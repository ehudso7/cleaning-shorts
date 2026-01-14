"""
Webhook handlers.
Only Stripe webhooks - no other integrations needed.

Handles:
- customer.subscription.created
- customer.subscription.updated
- customer.subscription.deleted

All subscription state is managed via webhooks.
No polling, no sync issues.
"""

import os
from fastapi import APIRouter, Request, HTTPException
import stripe

from ...lib import SubscriptionService


router = APIRouter()


@router.post("/stripe")
async def stripe_webhook(request: Request):
    """
    Handle Stripe webhook events.

    Verifies webhook signature for security.
    Updates local subscription state based on Stripe events.

    Events handled:
    - customer.subscription.created: Activate subscription
    - customer.subscription.updated: Update status (active/past_due/canceled)
    - customer.subscription.deleted: Mark as canceled

    All other events are acknowledged but ignored.
    """
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")
    webhook_secret = os.environ.get("STRIPE_WEBHOOK_SECRET")

    if not webhook_secret:
        raise HTTPException(status_code=500, detail="Webhook secret not configured")

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, webhook_secret
        )
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid payload")
    except stripe.error.SignatureVerificationError:
        raise HTTPException(status_code=400, detail="Invalid signature")

    service = SubscriptionService()

    # Handle subscription events
    if event.type == "customer.subscription.created":
        service.handle_subscription_created(event.data.object)

    elif event.type == "customer.subscription.updated":
        service.handle_subscription_updated(event.data.object)

    elif event.type == "customer.subscription.deleted":
        service.handle_subscription_deleted(event.data.object)

    # Acknowledge receipt
    return {"received": True}
