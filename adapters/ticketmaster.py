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
from domain.models import Plan


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


class TicketmasterAdapter:
    """Adapter for Ticketmaster Discovery API v2."""

    BASE_URL = "https://app.ticketmaster.com/discovery/v2"

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

        auth_url = "https://oauth.ticketmaster.com/oauth/token"
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
                if e.response.status_code >= 500 and attempt < max_retries - 1:
                    time.sleep(2 ** attempt)
                    continue
                raise ProviderError(f"Ticketmaster API error: {e}")

        raise ProviderError("Max retries exceeded")

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

        return response.get("_embedded", {}).get("events", [])

    def get_plan(self, plan_id: str) -> Optional[Dict[str, Any]]:
        """Get single plan by ID."""
        try:
            response = self._make_request("GET", f"/events/{plan_id}.json", use_cache=True)
            return response
        except PlanNotFoundError:
            return None

    def create_order(self, plan_id: str, quantity: int, seat_ids: List[str]) -> Dict[str, Any]:
        """Create order/offer with Ticketmaster (simulated for sandbox)."""
        # In sandbox, we simulate the TM order flow
        return {
            "id": f"tm_order_{plan_id}_{int(time.time())}",
            "status": "CREATED",
            "offer_id": f"offer_{plan_id}",
        }

    def accept_offer(self, offer_id: str) -> Dict[str, Any]:
        """Accept Ticketmaster offer (simulated for sandbox)."""
        return {
            "id": offer_id,
            "status": "ACCEPTED",
            "fulfillment": {"tickets": []},
        }


class PlanNotFoundError(Exception):
    """Plan not found in Ticketmaster."""
    pass


class ProviderError(Exception):
    """Provider API error."""
    pass