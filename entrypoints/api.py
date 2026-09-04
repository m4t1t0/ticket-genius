"""Flask API routes with OpenAPI documentation."""

from datetime import datetime
from uuid import UUID

from flask import Blueprint, jsonify, request
from flask_apispec import doc, marshal_with, use_kwargs

from entrypoints.schemas import (
    CancelOrderRequest,
    ConfirmPaymentRequest,
    CreateOrderRequest,
    ErrorResponse,
    OrderCreatedResponse,
    OrderStatusResponse,
    PaymentConfirmedResponse,
    PlanDetailResponse,
    PlanSearchResponse,
    RefundOrderRequest,
    SearchPlansRequest,
    SyncPlansResponse,
)
from service_layer import MessageBus
from service_layer.commands import (
    CancelOrderCommand,
    ConfirmPaymentCommand,
    CreateOrderCommand,
    RefundOrderCommand,
    SyncPlansCommand,
)
from service_layer.queries import GetOrderQuery, GetPlanQuery, SearchPlansQuery


def register_routes(message_bus: MessageBus) -> Blueprint:
    bp = Blueprint("api", __name__, url_prefix="/api/v1")

    # Error handlers
    @bp.errorhandler(400)
    def bad_request(e):
        return jsonify(
            ErrorResponse(
                type="https://tools.ietf.org/html/rfc7231#section-6.5.1",
                title="Bad Request",
                status=400,
                detail=str(e),
                instance=request.path,
            ).model_dump()
        ), 400

    @bp.errorhandler(404)
    def not_found(e):
        return jsonify(
            ErrorResponse(
                type="https://tools.ietf.org/html/rfc7231#section-6.5.4",
                title="Not Found",
                status=404,
                detail=str(e),
                instance=request.path,
            ).model_dump()
        ), 404

    @bp.errorhandler(500)
    def internal_error(e):
        return jsonify(
            ErrorResponse(
                type="https://tools.ietf.org/html/rfc7231#section-6.6.1",
                title="Internal Server Error",
                status=500,
                detail="An unexpected error occurred",
                instance=request.path,
            ).model_dump()
        ), 500

    # Domain exception handlers
    @bp.errorhandler(ValueError)
    def handle_value_error(e):
        # Check if it's a "not found" type error
        if "not found" in str(e).lower():
            return jsonify(
                ErrorResponse(
                    type="not_found",
                    title="Not Found",
                    status=404,
                    detail=str(e),
                    instance=request.path,
                ).model_dump()
            ), 404
        return jsonify(
            ErrorResponse(
                type="bad_request",
                title="Bad Request",
                status=400,
                detail=str(e),
                instance=request.path,
            ).model_dump()
        ), 400

    # Health check
    @bp.route("/health")
    @doc(summary="Health check", tags=["Health"])
    @marshal_with(ErrorResponse, code=500)
    def health():
        """Health check endpoint.
        ---
        get:
          summary: Health check
          description: Returns the health status of the API
          tags:
            - Health
          responses:
            200:
              description: API is healthy
              content:
                application/json:
                  schema:
                    type: object
                    properties:
                      status:
                        type: string
                        example: ok
        """
        return jsonify({"status": "ok"})

    # Orders
    @bp.route("/orders", methods=["POST"])
    @doc(summary="Create a new order", tags=["Orders"])
    @use_kwargs(CreateOrderRequest, location="json")
    @marshal_with(OrderCreatedResponse, code=201)
    @marshal_with(ErrorResponse, code=400)
    @marshal_with(ErrorResponse, code=404)
    def create_order():
        """Create a new order.
        ---
        post:
          summary: Create a new order
          description: Creates a new order for a plan with the specified quantity and attendee information
          tags:
            - Orders
          requestBody:
            required: true
            content:
              application/json:
                schema:
                  $ref: '#/components/schemas/CreateOrderRequest'
          responses:
            201:
              description: Order created successfully
              content:
                application/json:
                  schema:
                    $ref: '#/components/schemas/OrderCreatedResponse'
            400:
              description: Invalid request data
              content:
                application/json:
                  schema:
                    $ref: '#/components/schemas/ErrorResponse'
            404:
              description: Plan not found
              content:
                application/json:
                  schema:
                    $ref: '#/components/schemas/ErrorResponse'
        """
        data = CreateOrderRequest.model_validate(request.get_json())
        cmd = CreateOrderCommand(
            plan_id=data.plan_id,
            quantity=data.quantity,
            attendee_info=data.attendee_info.model_dump(),
            seat_ids=data.seat_ids,
        )
        result = message_bus.handle_command(cmd)
        return jsonify(OrderCreatedResponse.model_validate(result).model_dump()), 201

    @bp.route("/orders/<uuid:order_id>/confirm-payment", methods=["POST"])
    @doc(summary="Confirm payment for an order", tags=["Orders"])
    @use_kwargs(ConfirmPaymentRequest, location="json")
    @marshal_with(PaymentConfirmedResponse, code=200)
    @marshal_with(ErrorResponse, code=400)
    @marshal_with(ErrorResponse, code=404)
    def confirm_payment(order_id: UUID):
        """Confirm payment for an order.
        ---
        post:
          summary: Confirm payment for an order
          description: Confirms a payment for an existing order using the payment intent ID and idempotency key
          tags:
            - Orders
          parameters:
            - in: path
              name: order_id
              schema:
                type: string
                format: uuid
              required: true
              description: Order ID
          requestBody:
            required: true
            content:
              application/json:
                schema:
                  $ref: '#/components/schemas/ConfirmPaymentRequest'
          responses:
            200:
              description: Payment confirmed successfully
              content:
                application/json:
                  schema:
                    $ref: '#/components/schemas/PaymentConfirmedResponse'
            400:
              description: Invalid request data
              content:
                application/json:
                  schema:
                    $ref: '#/components/schemas/ErrorResponse'
            404:
              description: Order or payment not found
              content:
                application/json:
                  schema:
                    $ref: '#/components/schemas/ErrorResponse'
        """
        data = ConfirmPaymentRequest.model_validate(request.get_json())
        cmd = ConfirmPaymentCommand(
            order_id=order_id,
            payment_intent_id=data.payment_intent_id,
            idempotency_key=data.idempotency_key,
        )
        result = message_bus.handle_command(cmd)
        return jsonify(PaymentConfirmedResponse.model_validate(result).model_dump())

    @bp.route("/orders/<uuid:order_id>", methods=["GET"])
    @doc(summary="Get order status", tags=["Orders"])
    @marshal_with(OrderStatusResponse, code=200)
    @marshal_with(ErrorResponse, code=404)
    def get_order(order_id: UUID):
        """Get order status.
        ---
        get:
          summary: Get order status
          description: Retrieves the current status and details of an order
          tags:
            - Orders
          parameters:
            - in: path
              name: order_id
              schema:
                type: string
                format: uuid
              required: true
              description: Order ID
          responses:
            200:
              description: Order details retrieved successfully
              content:
                application/json:
                  schema:
                    $ref: '#/components/schemas/OrderStatusResponse'
            404:
              description: Order not found
              content:
                application/json:
                  schema:
                    $ref: '#/components/schemas/ErrorResponse'
        """
        query = GetOrderQuery(order_id=order_id)
        result = message_bus.handle_query(query)
        if not result:
            return jsonify(
                ErrorResponse(
                    type="not_found",
                    title="Order Not Found",
                    status=404,
                    detail=f"Order {order_id} not found",
                    instance=request.path,
                ).model_dump()
            ), 404
        return jsonify(OrderStatusResponse.model_validate(result).model_dump())

    @bp.route("/orders/<uuid:order_id>", methods=["DELETE"])
    @doc(summary="Cancel an order", tags=["Orders"])
    @use_kwargs(CancelOrderRequest, location="json")
    @marshal_with(ErrorResponse, code=400)
    @marshal_with(ErrorResponse, code=404)
    def cancel_order(order_id: UUID):
        """Cancel an order.
        ---
        delete:
          summary: Cancel an order
          description: Cancels an existing order with a reason
          tags:
            - Orders
          parameters:
            - in: path
              name: order_id
              schema:
                type: string
                format: uuid
              required: true
              description: Order ID
          requestBody:
            required: true
            content:
              application/json:
                schema:
                  $ref: '#/components/schemas/CancelOrderRequest'
          responses:
            204:
              description: Order cancelled successfully
            400:
              description: Invalid request data
              content:
                application/json:
                  schema:
                    $ref: '#/components/schemas/ErrorResponse'
            404:
              description: Order not found
              content:
                application/json:
                  schema:
                    $ref: '#/components/schemas/ErrorResponse'
        """
        data = CancelOrderRequest.model_validate(request.get_json())
        cmd = CancelOrderCommand(order_id=order_id, reason=data.reason)
        message_bus.handle_command(cmd)
        return "", 204

    @bp.route("/orders/<uuid:order_id>/refund", methods=["POST"])
    @doc(summary="Refund an order", tags=["Orders"])
    @use_kwargs(RefundOrderRequest, location="json")
    @marshal_with(ErrorResponse, code=400)
    @marshal_with(ErrorResponse, code=404)
    def refund_order(order_id: UUID):
        """Refund an order.
        ---
        post:
          summary: Refund an order
          description: Creates a refund for an order (full or partial)
          tags:
            - Orders
          parameters:
            - in: path
              name: order_id
              schema:
                type: string
                format: uuid
              required: true
              description: Order ID
          requestBody:
            required: true
            content:
              application/json:
                schema:
                  $ref: '#/components/schemas/RefundOrderRequest'
          responses:
            204:
              description: Refund created successfully
            400:
              description: Invalid request data
              content:
                application/json:
                  schema:
                    $ref: '#/components/schemas/ErrorResponse'
            404:
              description: Order not found
              content:
                application/json:
                  schema:
                    $ref: '#/components/schemas/ErrorResponse'
        """
        data = RefundOrderRequest.model_validate(request.get_json())
        amount = None
        if data.amount:
            from domain.value_objects import Currency, Money

            amount = Money(amount=data.amount.amount, currency=Currency(data.amount.currency))
        cmd = RefundOrderCommand(order_id=order_id, amount=amount, reason=data.reason)
        message_bus.handle_command(cmd)
        return "", 204

    # Plans
    @bp.route("/plans/search", methods=["GET"])
    @doc(summary="Search plans", tags=["Plans"])
    @marshal_with(PlanSearchResponse, code=200)
    def search_plans():
        """Search plans.
        ---
        get:
          summary: Search plans
          description: Search for plans/events with various filters
          tags:
            - Plans
          parameters:
            - in: query
              name: q
              schema:
                type: string
              description: Search query
            - in: query
              name: lat
              schema:
                type: number
              description: Latitude for location-based search
            - in: query
              name: lon
              schema:
                type: number
              description: Longitude for location-based search
            - in: query
              name: radius_km
              schema:
                type: integer
              description: Search radius in kilometers
            - in: query
              name: date_from
              schema:
                type: string
                format: date
              description: Filter events from this date
            - in: query
              name: date_to
              schema:
                type: string
                format: date
              description: Filter events to this date
            - in: query
              name: min_price
              schema:
                type: number
              description: Minimum price
            - in: query
              name: max_price
              schema:
                type: number
              description: Maximum price
            - in: query
              name: cursor
              schema:
                type: string
              description: Pagination cursor
            - in: query
              name: limit
              schema:
                type: integer
              description: Page size (max 100)
          responses:
            200:
              description: Search results
              content:
                application/json:
                  schema:
                    $ref: '#/components/schemas/PlanSearchResponse'
        """
        # Parse query params
        query_params = {
            "query": request.args.get("q"),
            "lat": request.args.get("lat", type=float),
            "lon": request.args.get("lon", type=float),
            "radius_km": request.args.get("radius_km", type=int),
            "date_from": request.args.get("date_from"),
            "date_to": request.args.get("date_to"),
            "min_price": request.args.get("min_price", type=float),
            "max_price": request.args.get("max_price", type=float),
            "cursor": request.args.get("cursor"),
            "limit": request.args.get("limit", 20, type=int),
        }
        # Remove None values
        query_params = {k: v for k, v in query_params.items() if v is not None}

        data = SearchPlansRequest.model_validate(query_params)
        query = SearchPlansQuery(
            query=data.query,
            lat=data.lat,
            lon=data.lon,
            radius_km=data.radius_km,
            date_from=data.date_from,
            date_to=data.date_to,
            min_price=data.min_price,
            max_price=data.max_price,
            cursor=data.cursor,
            limit=data.limit,
        )
        result = message_bus.handle_query(query)
        return jsonify(
            PlanSearchResponse(
                plans=[p for p in result],
                cursor=None,  # TODO: implement cursor
                has_more=len(result) >= data.limit,
            ).model_dump()
        )

    @bp.route("/plans/<uuid:plan_id>", methods=["GET"])
    @doc(summary="Get plan details", tags=["Plans"])
    @marshal_with(PlanDetailResponse, code=200)
    @marshal_with(ErrorResponse, code=404)
    def get_plan(plan_id: UUID):
        """Get plan details.
        ---
        get:
          summary: Get plan details
          description: Retrieves detailed information about a specific plan
          tags:
            - Plans
          parameters:
            - in: path
              name: plan_id
              schema:
                type: string
                format: uuid
              required: true
              description: Plan ID
          responses:
            200:
              description: Plan details retrieved successfully
              content:
                application/json:
                  schema:
                    $ref: '#/components/schemas/PlanDetailResponse'
            404:
              description: Plan not found
              content:
                application/json:
                  schema:
                    $ref: '#/components/schemas/ErrorResponse'
        """
        query = GetPlanQuery(plan_id=plan_id)
        result = message_bus.handle_query(query)
        if not result:
            return jsonify(
                ErrorResponse(
                    type="not_found",
                    title="Plan Not Found",
                    status=404,
                    detail=f"Plan {plan_id} not found",
                    instance=request.path,
                ).model_dump()
            ), 404
        return jsonify(PlanDetailResponse.model_validate(result).model_dump())

    # Admin
    @bp.route("/admin/sync-plans", methods=["POST"])
    @doc(summary="Sync plans from Ticketmaster", tags=["Admin"])
    @marshal_with(SyncPlansResponse, code=200)
    @marshal_with(ErrorResponse, code=400)
    def sync_plans():
        """Sync plans from Ticketmaster.
        ---
        post:
          summary: Sync plans from Ticketmaster
          description: Triggers a synchronization of plans from Ticketmaster API
          tags:
            - Admin
          requestBody:
            required: false
            content:
              application/json:
                schema:
                  type: object
                  properties:
                    since:
                      type: string
                      format: date-time
                      description: Sync plans modified since this date
                    stale_only:
                      type: boolean
                      description: Only sync stale plans
          responses:
            200:
              description: Sync completed
              content:
                application/json:
                  schema:
                    $ref: '#/components/schemas/SyncPlansResponse'
            400:
              description: Invalid request
              content:
                application/json:
                  schema:
                    $ref: '#/components/schemas/ErrorResponse'
        """
        data = request.get_json() or {}
        cmd = SyncPlansCommand(
            since=datetime.fromisoformat(data["since"]) if data.get("since") else None,
            stale_only=data.get("stale_only", False),
        )
        synced = message_bus.handle_command(cmd)
        return jsonify(
            SyncPlansResponse(synced_count=synced, message=f"Synced {synced} plans").model_dump()
        )

    return bp
