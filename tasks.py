import os
import signal
import subprocess
import sys
import time

import requests
from invoke import task

SERVER_PID_FILE = "/tmp/ticket_genius.pid"
WATCH_EXCLUDED = (".venv", "__pycache__", ".git")


def _looks_like_server(pid):
    """Check the PID still points at a Python/Flask process (guards against PID reuse)."""
    result = subprocess.run(["ps", "-p", str(pid), "-o", "comm="], capture_output=True, text=True)
    comm = result.stdout.strip().lower()
    return bool(comm) and ("python" in comm or "flask" in comm)


def _start_server(port, debug=False, capture_output=False):
    """Start the Flask server and wait until it responds."""
    if os.path.exists(SERVER_PID_FILE):
        os.remove(SERVER_PID_FILE)

    env = os.environ.copy()
    env["FLASK_APP"] = "app.py"
    env["FLASK_DEBUG"] = "1" if debug else "0"

    proc = subprocess.Popen(
        ["flask", "run", "--port", str(port)],
        env=env,
        stdout=subprocess.PIPE if capture_output else None,
        stderr=subprocess.PIPE if capture_output else None,
    )

    with open(SERVER_PID_FILE, "w") as f:
        f.write(str(proc.pid))

    for _ in range(30):
        try:
            requests.get(f"http://127.0.0.1:{port}/health", timeout=1)
            print(f"Flask server started on port {port} (PID: {proc.pid})")
            return proc
        except requests.exceptions.RequestException:
            time.sleep(0.5)

    print("Server failed to start in time")
    _stop_server()
    return None


def _stop_server(quiet=False):
    """Stop the Flask server via its PID file."""
    if not os.path.exists(SERVER_PID_FILE):
        if not quiet:
            print("No PID file found. Server may not be running.")
        return

    with open(SERVER_PID_FILE) as f:
        pid = int(f.read().strip())

    try:
        if not _looks_like_server(pid):
            print(f"PID {pid} is not a Flask/Python process (stale PID file); not killing")
        else:
            os.kill(pid, signal.SIGTERM)
            print(f"Stopped server (PID: {pid})")
    except ProcessLookupError:
        if not quiet:
            print(f"Process {pid} not found")
    finally:
        os.remove(SERVER_PID_FILE)


@task
def start(c, port=5000, debug=False):
    """Start the Flask server."""
    if os.path.exists(SERVER_PID_FILE):
        print("Server already running (PID file exists). Use `invoke stop` first.")
        return
    _start_server(port, debug=debug, capture_output=True)


@task
def stop(c):
    """Stop the Flask server."""
    _stop_server()


@task
def restart(c, port=5000, debug=False):
    """Restart the Flask server."""
    stop(c)
    start(c, port=port, debug=debug)


@task
def debug(c, port=5000):
    """Start the Flask server with hot reload (debug mode)."""
    start(c, port=port, debug=True)


@task
def test(c, verbose=False, coverage=False, unit=False, integration=False):
    """Run tests with pytest."""
    cmd = ["python", "-m", "pytest"]
    if verbose:
        cmd.append("-v")
    if coverage:
        cmd.extend(
            ["--cov=domain", "--cov=adapters", "--cov=service_layer", "--cov-report=term-missing"]
        )
    if unit:
        cmd.extend(["tests/unit"])
    if integration:
        cmd.extend(["tests/integration"])
    c.run(" ".join(cmd), pty=True)


@task
def watch(c, port=5000):
    """Start server with auto-reload using watchfiles."""
    from watchfiles import watch

    print(f"Starting file watcher on port {port}...")
    print("Watching for .py file changes...")

    def py_filter(change, path):
        p = str(path)
        return p.endswith(".py") and not any(part in p for part in WATCH_EXCLUDED)

    proc = _start_server(port)

    try:
        for changes in watch(".", watch_filter=py_filter):
            print(f"\nChanges detected: {changes}")
            print("Restarting server...")
            _stop_server(quiet=True)
            proc = _start_server(port)
            print("Server restarted.")
    except KeyboardInterrupt:
        print("\nStopping watcher...")
        _stop_server(quiet=True)


@task
def cli(c, *args):
    """Run admin CLI commands. Usage: invoke cli -- sync-plans --help"""
    from cli.commands import cli as click_cli

    sys.argv = ["cli"] + list(args)
    click_cli()


@task
def sync_plans(c, since=None, stale_only=False, full=False):
    """Sync plans from Ticketmaster."""

    sys.argv = ["cli", "sync-plans"]
    if since:
        sys.argv.extend(["--since", since])
    if stale_only:
        sys.argv.append("--stale-only")
    if full:
        sys.argv.append("--full")
    from cli.commands import cli as click_cli

    click_cli()


@task
def purge_cache(c, pattern="*"):
    """Purge Redis cache by pattern."""

    sys.argv = ["cli", "purge-cache", "--pattern", pattern]
    from cli.commands import cli as click_cli

    click_cli()


@task
def toggle_flag(c, flag_name, value, pct=100):
    """Toggle feature flag."""

    sys.argv = ["cli", "toggle-flag", flag_name, value, "--pct", str(pct)]
    from cli.commands import cli as click_cli

    click_cli()
