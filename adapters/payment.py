"""Payment adapter (simulated for development)."""
import time
from dataclasses import dataclass
from decimal import Decimal
from typing import Dict, Optional
from uuid import UUID, uuid4

from domain.value_objects import Money, Currency


@dataclass
class PaymentIntent:
    id: str
    client_secret: str
    status: str
    amount: Money
    metadata: Dict


class PaymentSimulatorAdapter:
    """Simulated payment adapter for development/testing."""

    def __init__(self):
        self._intents: Dict[str, PaymentIntent] = {}

    def create_payment_intent(
        self,
        amount: Money,
        currency: Currency,
        metadata: Optional[Dict] = None,
    ) -> PaymentIntent:
        """Create a simulated payment intent."""
        intent_id = f"pi_test_{uuid4().hex[:24]}"
        client_secret = f"{intent_id}_secret_{uuid4().hex[:16]}"

        intent = PaymentIntent(
            id=intent_id,
            client_secret=client_secret,
            status="requires_payment_method",
            amount=amount,
            metadata=metadata or {},
        )

        self._intents[intent_id] = intent
        return intent

    def confirm_payment(
        self,
        payment_intent_id: str,
        payment_method: str = "pm_card_visa",
    ) -> PaymentIntent:
        """Confirm a simulated payment."""
        intent = self._intents.get(payment_intent_id)
        if not intent:
            raise PaymentNotFoundError(f"Payment intent {payment_intent_id} not found")

        # Simulate failure for amounts > €100
        if intent.amount.amount > Decimal("100"):
            intent.status = "failed"
            intent.metadata["failure_reason"] = "amount_exceeds_limit"
        else:
            intent.status = "succeeded"
            intent.metadata["payment_method"] = payment_method
            intent.metadata["captured_at"] = str(int(time.time()))

        return intent

    def get_payment_intent(self, payment_intent_id: str) -> Optional[PaymentIntent]:
        """Get payment intent by ID."""
        return self._intents.get(payment_intent_id)


class PaymentNotFoundError(Exception):
    """Payment intent not found."""
    pass


class PaymentProviderError(Exception):
    """Payment provider error."""
    pass


# For future Stripe integration:
"""
class StripeAdapter:
    def __init__(self, api_key: str):
        import stripe
        self.stripe = stripe
        self.stripe.api_key = api_key

    def create_payment_intent(self, amount, currency, metadata):
        intent = self.stripe.PaymentIntent.create(
            amount=int(amount.amount * 100),
            currency=currency.value.lower(),
            metadata=metadata,
            automatic_payment_methods={"enabled": True},
        )
        return PaymentIntent(
            id=intent.id,
            client_secret=intent.client_secret,
            status=intent.status,
            amount=amount,
            metadata=metadata,
        )

    def confirm_payment(self, payment_intent_id, payment_method):
        intent = self.stripe.PaymentIntent.confirm(
            payment_intent_id,
            payment_method=payment_method,
        )
        return PaymentIntent(
            id=intent.id,
            client_secret=intent.client_secret,
            status=intent.status,
            amount=Money(Decimal(str(intent.amount)) / 100, Currency(intent.currency.upper())),
            metadata=intent.metadata,
        )
"""