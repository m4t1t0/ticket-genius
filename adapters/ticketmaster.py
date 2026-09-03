"""Ticketmaster Discovery API adapter."""
import time
import hashlib
import json
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from urllib.parse import urlencode

import httpx
from redis import Redis

from domain.value_objects import Money, Currency, DateRange
from domain.exceptions import PlanNotFoundError, ProviderError, ProviderRateLimitedError, ProviderAuthenticationError
from domain.repositories import PlanSearchPort


class TokenBucket:
    """Simple token bucket rate limiter."""

    def __init__(self, capacity: int = 5, refill_rate: float = 5.0):
        self.capacity = capacity
        self.refill_rate = refill_rate
        self._tokens = capacity
        self._last_refill = time.monotonic()

    def consume(self, tokens: int = 1) -> float:
        """Consume tokens, return wait time if needed."""
        now = time.monotonic()
        elapsed = now - self._last_refill
        self._tokens = min(self.capacity, self._tokens + elapsed * self.refill_rate)
        self._last_refill = now

        if self._tokens >= tokens:
            self._tokens -= tokens
            return 0.0

        deficit = tokens - self._tokens
        wait_time = deficit / self.refill_rate
        self._tokens = 0
        return wait_time


class TicketmasterAdapter(PlanSearchPort):
    """Adapter for Ticketmaster Discovery API v2.

    Note: The Discovery API v2 uses the same base URL for both sandbox and production.
    The environment is determined by the API credentials (client_id/client_secret).
    Sandbox credentials are obtained from the Ticketmaster Developer Portal.
    
    Implements PlanSearchPort for external provider search.
    """

    BASE_URL = "https://app.ticketmaster.com/discovery/v2"
    OAUTH_URL = "https://oauth.ticketmaster.com/oauth/token"

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        redis_client: Optional[Redis] = None,
        sandbox: bool = True,
    ):
        self.client_id = client_id
        self.client_secret = client_secret
        self.redis = redis_client
        self.sandbox = sandbox

        self._http_client = httpx.Client(
            base_url=self.BASE_URL,
            timeout=httpx.Timeout(10.0, connect=30.0),
        )

        self._rate_limiter = TokenBucket(capacity=5, refill_rate=5.0)
        self._access_token: Optional[str] = None
        self._token_expires_at: float = 0

    def _get_access_token(self) -> str:
        """Get OAuth2 access token using client credentials."""
        if self._access_token and time.time() < self._token_expires_at - 300:  # 5min buffer
            return self._access_token

        # Use same OAuth endpoint for both sandbox and production
        # Environment is determined by client credentials
        auth_url = self.OAUTH_URL
        data = {
            "grant_type": "client_credentials",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
        }

        response = httpx.post(auth_url, data=data, timeout=10.0)
        response.raise_for_status()

        token_data = response.json()
        self._access_token = token_data["access_token"]
        expires_in = token_data.get("expires_in", 3600)
        self._token_expires_at = time.time() + expires_in

        return self._access_token

    def _make_request(
        self,
        method: str,
        path: str,
        params: Optional[Dict] = None,
        use_cache: bool = True,
    ) -> Dict[str, Any]:
        """Make HTTP request with rate limiting, caching, and retries."""
        params = params or {}
        params["apikey"] = self.client_id

        # Generate cache key
        cache_key = None
        if use_cache and self.redis:
            cache_key = self._cache_key(method, path, params)
            cached = self.redis.get(cache_key)
            if cached:
                return json.loads(cached)

        # Rate limiting
        wait_time = self._rate_limiter.consume()
        if wait_time > 0:
            time.sleep(wait_time)

        # Make request with retries
        max_retries = 3
        for attempt in range(max_retries):
            try:
                response = self._http_client.request(
                    method,
                    path,
                    params=params,
                    headers={"Authorization": f"Bearer {self._get_access_token()}"},
                )

                if response.status_code == 429:
                    retry_after = int(response.headers.get("Retry-After", "60"))
                    time.sleep(min(retry_after, 60))
                    continue

                if response.status_code >= 500:
                    if attempt < max_retries - 1:
                        time.sleep(2 ** attempt)
                        continue

                response.raise_for_status()
                data = response.json()

                # Cache successful GET responses
                if use_cache and self.redis and cache_key and method == "GET":
                    self.redis.setex(cache_key, 300, json.dumps(data))

                return data

            except httpx.HTTPStatusError as e:
                if e.response.status_code == 404:
                    raise PlanNotFoundError("Plan not found")
                if e.response.status_code == 401:
                    raise ProviderAuthenticationError("Ticketmaster")
                if e.response.status_code == 429:
                    retry_after = int(e.response.headers.get("Retry-After", "60"))
                    raise ProviderRateLimitedError("Ticketmaster", retry_after=retry_after)
                if e.response.status_code >= 500 and attempt < max_retries - 1:
                    time.sleep(2 ** attempt)
                    continue
                raise ProviderError("Ticketmaster", str(e))

        raise ProviderError("Ticketmaster", "Max retries exceeded")

    def _cache_key(self, method: str, path: str, params: Dict) -> str:
        """Generate cache key for request."""
        # Normalize params for consistent hashing
        normalized = {k: v for k, v in sorted(params.items()) if k != "apikey"}
        key_str = f"{method}:{path}:{urlencode(normalized)}"
        return f"tm:search:{hashlib.sha256(key_str.encode()).hexdigest()[:32]}"

    def search_plans(
        self,
        query: Optional[str] = None,
        lat: Optional[float] = None,
        lon: Optional[float] = None,
        radius_km: Optional[int] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        min_price: Optional[float] = None,
        max_price: Optional[float] = None,
        page: int = 0,
        size: int = 20,
    ) -> List[Dict[str, Any]]:
        """Search for plans/events."""
        params = {"page": page, "size": min(size, 100)}

        if query:
            params["keyword"] = query
        if lat is not None and lon is not None:
            params["latlong"] = f"{lat},{lon}"
        if radius_km is not None:
            params["radius"] = radius_km
            params["unit"] = "km"
        if date_from:
            params["startDateTime"] = date_from
        if date_to:
            params["endDateTime"] = date_to
        if min_price is not None:
            params["minPrice"] = int(min_price * 100)
        if max_price is not None:
            params["maxPrice"] = int(max_price * 100)

        response = self._make_request("GET", "/events.json", params, use_cache=True)

        events = response.get("_embedded", {}).get("events", [])
        
        # Cache individual events from search results
        for event in events:
            self._cache_event(event)
        
        return events

    def get_plan(self, plan_id: str) -> Optional[Dict[str, Any]]:
        """Get single plan by ID."""
        # Try cache first
        cached = self.get_cached_event(plan_id)
        if cached:
            return cached
        
        try:
            response = self._make_request("GET", f"/events/{plan_id}.json", use_cache=True)
            # Cache the response
            self._cache_event(response)
            return response
        except PlanNotFoundError:
            return None

    # --- Event cache methods (tm:event:{id}) ---

    def _cache_event(self, event_data: Dict[str, Any]) -> None:
        """Cache event data with key tm:event:{id}."""
        if not self.redis:
            return
        event_id = event_data.get("id")
        if not event_id:
            return
        cache_key = f"tm:event:{event_id}"
        self.redis.setex(cache_key, 300, json.dumps(event_data))  # 5 min TTL

    def get_cached_event(self, event_id: str) -> Optional[Dict[str, Any]]:
        """Get event from cache by ID."""
        if not self.redis:
            return None
        cache_key = f"tm:event:{event_id}"
        cached = self.redis.get(cache_key)
        if cached:
            return json.loads(cached)
        return None

    def invalidate_event_cache(self, event_id: str) -> None:
        """Invalidate event cache (called on webhook)."""
        if not self.redis:
            return
        cache_key = f"tm:event:{event_id}"
        self.redis.delete(cache_key)

    def invalidate_all_event_cache(self) -> None:
        """Invalidate all event caches (called on full sync)."""
        if not self.redis:
            return
        # Use SCAN to find and delete all tm:event:* keys
        cursor = 0
        while True:
            cursor, keys = self.redis.scan(cursor, match="tm:event:*", count=100)
            if keys:
                self.redis.delete(*keys)
            if cursor == 0:
                break

    # Webhook handler for event updates
    def handle_plan_updated_webhook(self, event_id: str) -> None:
        """Handle TM plan update webhook - invalidate cache for the event."""
        self.invalidate_event_cache(event_id)
        # Also invalidate search cache
        if self.redis:
            cursor = 0
            while True:
                cursor, keys = self.redis.scan(cursor, match="tm:search:*", count=100)
                if keys:
                    self.redis.delete(*keys)
                if cursor == 0:
                    break

    def create_order(
        self,
        plan_id: str,
        quantity: int,
        seat_ids: List[str],
        idempotency_key: str,
    ) -> Dict[str, Any]:
        """Create order/offer with Ticketmaster Commerce API.

        Uses idempotency key to prevent duplicate orders.
        In sandbox, simulates the TM Commerce API flow.
        """
        # Check idempotency
        if self.redis:
            idempotency_cache_key = f"tm:offer:{idempotency_key}"
            cached = self.redis.get(idempotency_cache_key)
            if cached:
                return json.loads(cached)

        # In production, this would call TM Commerce API:
        # POST /commerce/v2/offers with idempotency-key header
        # For sandbox, simulate the response
        tm_order_id = f"tm_order_{plan_id}_{int(time.time())}"
        offer_id = f"offer_{plan_id}_{idempotency_key[:8]}"

        result = {
            "id": tm_order_id,
            "status": "CREATED",
            "offer_id": offer_id,
            "quantity": quantity,
            "seat_ids": seat_ids,
        }

        # Cache with idempotency key (24h TTL)
        if self.redis:
            self.redis.setex(idempotency_cache_key, 86400, json.dumps(result))

        return result

    def accept_offer(self, offer_id: str, idempotency_key: str, seat_ids: Optional[List[str]] = None) -> Dict[str, Any]:
        """Accept Ticketmaster offer (simulated for sandbox).

        Uses idempotency key to prevent duplicate acceptances.
        """
        # Check idempotency
        if self.redis:
            idempotency_cache_key = f"tm:accept:{idempotency_key}"
            cached = self.redis.get(idempotency_cache_key)
            if cached:
                return json.loads(cached)

        # In production, this would call TM Commerce API:
        # POST /commerce/v2/offers/{offer_id}/accept with idempotency-key header
        # For sandbox, simulate the response with fulfillment
        seat_ids = seat_ids or []
        result = {
            "id": offer_id,
            "status": "ACCEPTED",
            "fulfillment": {
                "tickets": [
                    {
                        "id": f"ticket_{offer_id}_{i}",
                        "seat_id": seat_ids[i] if i < len(seat_ids) else f"GA-{i}",
                        "barcode": f"BC-{offer_id}-{i}",
                    }
                    for i in range(1)  # Simplified: 1 ticket per offer
                ]
            },
        }

        # Cache with idempotency key (24h TTL)
        if self.redis:
            self.redis.setex(idempotency_cache_key, 86400, json.dumps(result))

        return result

    def update_plan_from_ticketmaster(self, plan, tm_data: dict) -> None:
        """
        Update a Plan aggregate from Ticketmaster data.
        
        This logic belongs in the adapter, not the domain aggregate,
        to maintain the Provider-Agnostic Domain principle.
        """
        from decimal import Decimal
        from datetime import datetime, timezone
        
        plan.name = tm_data["name"]
        plan.url = tm_data["url"]
        plan.image_url = tm_data["images"][0]["url"] if tm_data.get("images") else None
        plan.venue_name = tm_data["_embedded"]["venues"][0]["name"]
        plan.venue_city = tm_data["_embedded"]["venues"][0]["city"]["name"]
        plan.venue_state = tm_data["_embedded"]["venues"][0]["state"]["name"]
        price_range = tm_data.get("priceRanges", [{}])[0]
        plan.min_price = Money(Decimal(str(price_range.get("min", 0))), Currency.EUR)
        plan.max_price = Money(Decimal(str(price_range.get("max", 0))), Currency.EUR)
        plan.last_synced_at = datetime.now(timezone.utc)
        plan.tm_last_modified = datetime.fromisoformat(tm_data["lastUpdated"].replace("Z", "+00:00"))
        plan.version += 1
        # TM doesn't provide per-section pricing, keep existing or initialize empty
        if not hasattr(plan, 'seat_prices_json') or plan.seat_prices_json is None:
            plan.seat_prices_json = {}