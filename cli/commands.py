"""Admin CLI commands."""
import click
import json
import sys
from datetime import datetime, timedelta
from uuid import UUID

from entrypoints import create_app


@click.group()
def cli():
    """Ticket Genius Admin CLI."""
    pass


@cli.command()
@click.option('--since', type=click.DateTime(), help='Sync plans modified since this date')
@click.option('--stale-only', is_flag=True, help='Only sync stale plans (>24h old)')
@click.option('--full', is_flag=True, help='Full sync from beginning')
def sync_plans(since, stale_only, full):
    """Sync plans from Ticketmaster."""
    app = create_app()
    with app.app_context():
        from service_layer import MessageBus
        from service_layer.commands import SyncPlansCommand
        from entrypoints.bootstrap import bootstrap
        
        message_bus = bootstrap()
        
        if full:
            since = None
            stale_only = False
        
        cmd = SyncPlansCommand(since=since, stale_only=stale_only)
        try:
            synced = message_bus.handle_command(cmd)
            click.echo(json.dumps({"synced": synced, "message": f"Synced {synced} plans"}))
        except Exception as e:
            click.echo(json.dumps({"error": str(e)}), err=True)
            sys.exit(1)


@cli.command()
@click.option('--pattern', default='*', help='Cache key pattern to purge')
def purge_cache(pattern):
    """Purge Redis cache by pattern."""
    app = create_app()
    with app.app_context():
        import os
        from redis import Redis
        
        redis_url = os.getenv("REDIS_URL")
        if not redis_url:
            click.echo(json.dumps({"error": "REDIS_URL not configured"}), err=True)
            sys.exit(1)
        
        redis = Redis.from_url(redis_url, decode_responses=True)
        keys = redis.keys(pattern)
        if keys:
            redis.delete(*keys)
            click.echo(json.dumps({"purged": len(keys), "keys": keys}))
        else:
            click.echo(json.dumps({"purged": 0, "message": "No keys matched"}))


@cli.command()
@click.argument('flag_name')
@click.argument('value', type=click.Choice(['on', 'off']))
@click.option('--pct', type=int, default=100, help='Rollout percentage')
def toggle_flag(flag_name, value, pct):
    """Toggle feature flag."""
    app = create_app()
    with app.app_context():
        import os
        from redis import Redis
        import json
        
        redis_url = os.getenv("REDIS_URL")
        if not redis_url:
            click.echo(json.dumps({"error": "REDIS_URL not configured"}), err=True)
            sys.exit(1)
        
        redis = Redis.from_url(os.getenv("REDIS_URL"), decode_responses=True)
        flag_data = {"enabled": value == "on", "rollout_pct": pct}
        redis.set(f"FF:{flag_name}", json.dumps(flag_data))
        click.echo(json.dumps({"flag": flag_name, **flag_data}))


@cli.command()
@click.argument('order_id')
@click.argument('amount')
@click.argument('reason', type=click.Choice(['CUSTOMER_REQUEST', 'EVENT_CANCELLED', 'SEAT_ISSUE']))
def create_refund(order_id, amount, reason):
    """Create a refund for an order."""
    app = create_app()
    with app.app_context():
        from service_layer import MessageBus
        from service_layer.commands import RefundOrderCommand
        from entrypoints.bootstrap import bootstrap
        from domain.value_objects import Money, Currency
        
        message_bus = bootstrap()
        
        cmd = RefundOrderCommand(
            order_id=order_id,
            amount=Money(amount=int(float(amount) * 100), currency=Currency.EUR),
            reason=reason,
        )
        
        try:
            message_bus.handle_command(cmd)
            click.echo(json.dumps({"message": f"Refund created for order {order_id}"}))
        except Exception as e:
            click.echo(json.dumps({"error": str(e)}), err=True)
            sys.exit(1)


@cli.command()
@click.argument('from_id', required=False)
def replay_outbox(from_id):
    """Replay outbox events from a given ID."""
    app = create_app()
    with app.app_context():
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
        from adapters.orm import OutboxEvent
        import os
        import json
        
        database_url = os.getenv("DATABASE_URL")
        engine = create_engine(database_url)
        Session = sessionmaker(bind=engine)
        session = Session()
        
        query = session.query(OutboxEvent).filter(OutboxEvent.processed_at.is_(None))
        if from_id:
            query = query.filter(OutboxEvent.id >= from_id)
        
        events = query.order_by(OutboxEvent.created_at).limit(100).all()
        
        for event in events:
            click.echo(json.dumps({
                "id": str(event.id),
                "aggregate_id": str(event.aggregate_id),
                "aggregate_type": event.aggregate_type,
                "event_type": event.event_type,
                "payload": event.payload,
                "created_at": event.created_at.isoformat(),
            }))
        
        session.close()


@cli.command()
def health_check():
    """Run health checks."""
    app = create_app()
    with app.app_context():
        import os
        import json
        from sqlalchemy import create_engine, text
        from redis import Redis
        
        checks = {"status": "ok", "checks": {}}
        overall_ok = True
        
        # Database
        try:
            database_url = os.getenv("DATABASE_URL")
            engine = create_engine(database_url)
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            checks["checks"]["database"] = {"status": "ok"}
        except Exception as e:
            checks["checks"]["database"] = {"status": "fail", "error": str(e)}
            overall_ok = False
        
        # Redis
        try:
            redis_url = os.getenv("REDIS_URL")
            if redis_url:
                redis = Redis.from_url(os.getenv("REDIS_URL"), decode_responses=True)
                redis.ping()
                checks["checks"]["redis"] = {"status": "ok"}
            else:
                checks["checks"]["redis"] = {"status": "skip", "reason": "not configured"}
        except Exception as e:
            checks["checks"]["redis"] = {"status": "fail", "error": str(e)}
            overall_ok = False
        
        checks["status"] = "ok" if overall_ok else "degraded"
        click.echo(json.dumps(checks, indent=2))
        
        if not overall_ok:
            sys.exit(1)


@cli.command()
@click.option('--threshold-hours', default=24, help='Hours threshold for staleness')
def check_stale(threshold_hours):
    """Check for stale plans that haven't been synced recently."""
    import os
    import json
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from adapters.orm import Plan
    from datetime import datetime, timedelta, timezone
    
    database_url = os.getenv("DATABASE_URL")
    engine = create_engine(database_url)
    Session = sessionmaker(bind=engine)
    session = Session()
    
    try:
        threshold = datetime.now(timezone.utc) - timedelta(hours=threshold_hours)
        stale_plans = session.query(Plan).filter(
            Plan.last_synced_at < threshold
        ).all()
        
        stale_data = []
        for plan in stale_plans:
            stale_data.append({
                "plan_id": str(plan.plan_id),
                "tm_plan_id": plan.tm_plan_id,
                "name": plan.name,
                "last_synced_at": plan.last_synced_at.isoformat() if plan.last_synced_at else None,
                "hours_stale": int((datetime.now(timezone.utc) - plan.last_synced_at).total_seconds() / 3600) if plan.last_synced_at else None,
            })
        
        click.echo(json.dumps({
            "stale_count": len(stale_data),
            "threshold_hours": threshold_hours,
            "stale_plans": stale_data,
        }, indent=2))
        
    except Exception as e:
        click.echo(json.dumps({"error": str(e)}), err=True)
        sys.exit(1)
    finally:
        session.close()


@cli.command()
@click.option('--threshold-hours', default=24, help='Hours threshold for staleness')
@click.option('--dry-run', is_flag=True, help='Only show what would be synced, do not sync')
def sync_stale(threshold_hours, dry_run):
    """Sync only stale plans (older than threshold hours)."""
    import json
    
    app = create_app()
    with app.app_context():
        from service_layer import MessageBus
        from service_layer.commands import SyncPlansCommand
        from entrypoints.bootstrap import bootstrap
        
        message_bus = bootstrap()
        
        if dry_run:
            # Just show what would be synced
            import os
            from sqlalchemy import create_engine
            from sqlalchemy.orm import sessionmaker
            from adapters.orm import Plan
            from datetime import datetime, timedelta, timezone
            
            database_url = os.getenv("DATABASE_URL")
            engine = create_engine(database_url)
            Session = sessionmaker(bind=engine)
            session = Session()
            
            try:
                threshold = datetime.now(timezone.utc) - timedelta(hours=threshold_hours)
                stale_plans = session.query(Plan).filter(
                    Plan.last_synced_at < threshold
                ).all()
                
                stale_data = [{
                    "plan_id": str(p.plan_id),
                    "tm_plan_id": p.tm_plan_id,
                    "name": p.name,
                    "last_synced_at": p.last_synced_at.isoformat() if p.last_synced_at else None,
                } for p in stale_plans]
                
                click.echo(json.dumps({
                    "would_sync": len(stale_data),
                    "threshold_hours": threshold_hours,
                    "plans": stale_data,
                }, indent=2))
            finally:
                session.close()
            return
        
        # Actual sync
        cmd = SyncPlansCommand(stale_only=True)
        try:
            synced = message_bus.handle_command(cmd)
            click.echo(json.dumps({"synced": synced, "message": f"Synced {synced} stale plans"}))
        except Exception as e:
            click.echo(json.dumps({"error": str(e)}), err=True)
            sys.exit(1)


if __name__ == "__main__":
    cli()