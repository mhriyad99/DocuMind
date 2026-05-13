from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional


# ── Data shapes ───────────────────────────────────────────────────────────────

@dataclass
class CheckoutResult:
    """
    Returned by create_checkout().
    Redirect the user to `checkout_url` to complete payment.
    `session_id` is gateway-specific — store it if you need to
    reconcile later (e.g. Stripe session ID before the webhook fires).
    """
    checkout_url: str
    session_id: Optional[str] = None


@dataclass
class WebhookEvent:
    """
    Normalised event passed to your route handler after handle_webhook()
    validates and parses the raw gateway payload.

    event_type maps to a small set of actions your app cares about:
        subscription.activated  — new subscription confirmed, activate access
        subscription.renewed    — billing cycle renewed successfully
        subscription.past_due   — payment failed, start grace period
        subscription.cancelled  — user or gateway cancelled
        subscription.expired    — grace period elapsed, revoke access

    gateway_customer_id and gateway_subscription_id are the raw IDs
    from the gateway — write them into your subscriptions table.
    """
    event_type: str
    user_id: Optional[str]                  # your internal user UUID
    plan_id: Optional[str]                  # your internal plan UUID
    gateway_customer_id: Optional[str]
    gateway_subscription_id: Optional[str]
    raw_payload: dict                        # full original payload for logging


# ── Base class ────────────────────────────────────────────────────────────────

class PaymentGateway(ABC):
    """
    Abstract payment gateway. All billing routes talk to this interface only —
    never to Stripe or SSLCommerz directly.

    To add a new gateway:
        1. Subclass PaymentGateway
        2. Implement create_checkout() and handle_webhook()
        3. Add a branch in get_gateway() in this file
        4. Set PAYMENT_GATEWAY in your .env

    Nothing else in the codebase changes.
    """

    @abstractmethod
    async def create_checkout(
        self,
        user_id: str,
        user_email: str,
        plan_id: str,
        stripe_price_id: Optional[str],
        success_url: str,
        cancel_url: str,
    ) -> CheckoutResult:
        """
        Initiate a checkout session for the given user + plan.

        Returns a CheckoutResult with the URL to redirect the user to.
        The user completes payment on the gateway's hosted page.
        Your app finds out the result via handle_webhook(), not here.
        """
        raise NotImplementedError

    @abstractmethod
    async def handle_webhook(
        self,
        raw_body: bytes,
        headers: dict,
    ) -> Optional[WebhookEvent]:
        """
        Validate the incoming webhook/callback from the gateway.
        Verify the signature. Parse the payload.
        Return a normalised WebhookEvent, or None if the event is
        irrelevant (e.g. an event type your app doesn't act on).

        Raise ValueError if signature validation fails — your route
        handler should return 400 in that case.
        """
        raise NotImplementedError

    @abstractmethod
    async def create_portal_url(
        self,
        gateway_customer_id: str,
        return_url: str,
    ) -> str:
        """
        Return a URL to the gateway's self-serve billing portal
        where the user can update their card, cancel, or download invoices.

        Not all gateways support this — raise NotImplementedError if yours
        doesn't, and handle it gracefully in the route.
        """
        raise NotImplementedError


# ── Stripe (to be implemented) ────────────────────────────────────────────────

class StripeGateway(PaymentGateway):
    """
    Stripe implementation.

    Install:  pip install stripe
    Docs:     https://stripe.com/docs/api
    Webhooks: stripe listen --forward-to localhost:8000/billing/webhook
    """

    async def create_checkout(self, user_id, user_email, plan_id,
                              stripe_price_id, success_url, cancel_url) -> CheckoutResult:
        raise NotImplementedError("StripeGateway.create_checkout not yet implemented")

    async def handle_webhook(self, raw_body, headers) -> Optional[WebhookEvent]:
        raise NotImplementedError("StripeGateway.handle_webhook not yet implemented")

    async def create_portal_url(self, gateway_customer_id, return_url) -> str:
        raise NotImplementedError("StripeGateway.create_portal_url not yet implemented")


# ── SSLCommerz (to be implemented) ───────────────────────────────────────────

class SSLCommerzGateway(PaymentGateway):
    """
    SSLCommerz implementation.

    Sandbox:  https://developer.sslcommerz.com
    Docs:     https://developer.sslcommerz.com/doc/v4
    Note:     SSLCommerz is redirect-based — no webhook push.
              handle_webhook() here handles the POST to your
              success/fail/cancel URLs after the user is redirected back.
    """

    async def create_checkout(self, user_id, user_email, plan_id,
                              stripe_price_id, success_url, cancel_url) -> CheckoutResult:
        raise NotImplementedError("SSLCommerzGateway.create_checkout not yet implemented")

    async def handle_webhook(self, raw_body, headers) -> Optional[WebhookEvent]:
        raise NotImplementedError("SSLCommerzGateway.handle_webhook not yet implemented")

    async def create_portal_url(self, gateway_customer_id, return_url) -> str:
        # SSLCommerz has no self-serve portal — route should handle this gracefully
        raise NotImplementedError("SSLCommerz does not support a billing portal")


# ── Factory ───────────────────────────────────────────────────────────────────

def get_gateway() -> PaymentGateway:
    """
    Returns the configured gateway instance.
    Import and call this in your billing routes — never import
    StripeGateway or SSLCommerzGateway directly in route files.

    Controlled by PAYMENT_GATEWAY in your .env:
        PAYMENT_GATEWAY=stripe       (default)
        PAYMENT_GATEWAY=sslcommerz
    """
    from app.core.config import settings

    gateways = {
        "stripe": StripeGateway,
        "sslcommerz": SSLCommerzGateway,
    }

    cls = gateways.get(settings.PAYMENT_GATEWAY)
    if cls is None:
        raise ValueError(
            f"Unknown PAYMENT_GATEWAY '{settings.PAYMENT_GATEWAY}'. "
            f"Valid options: {list(gateways.keys())}"
        )
    return cls()