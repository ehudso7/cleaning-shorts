"""
Subscription management routes.
All self-serve - no support tickets needed.

Endpoints:
- GET /status - Current subscription status
- POST /checkout - Start subscription
- POST /cancel - Cancel at period end
- POST /refund - Self-serve refund (within 7 days)
- GET /portal - Stripe billing portal URL
"""

import os
from fastapi import APIRouter, Depends, HTTPException, Request

from ...lib import SubscriptionService, get_current_user
from ...models import SubscriptionRequest, RefundRequest


router = APIRouter()


@router.get("/status")
async def get_subscription_status(
    user: dict = Depends(get_current_user)
):
    """
    Get current subscription status.

    Returns:
    - status: active, canceled, past_due, trialing
    - started_at: When subscription started
    - ends_at: When access ends (if canceled)
    - can_refund: Whether eligible for self-serve refund
    """
    service = SubscriptionService()
    return service.get_subscription_status(user["id"])


@router.post("/checkout")
async def create_checkout_session(
    request: Request,
    body: SubscriptionRequest,
    user: dict = Depends(get_current_user)
):
    """
    Create Stripe Checkout session for subscription.

    Body:
    - price_id: Stripe price ID (monthly or yearly)

    Returns:
    - checkout_url: Redirect user here to complete payment

    Use STRIPE_PRICE_MONTHLY or STRIPE_PRICE_YEARLY from env.
    """
    service = SubscriptionService()

    # Build URLs
    base_url = str(request.base_url).rstrip("/")
    success_url = f"{base_url}/subscription/success"
    cancel_url = f"{base_url}/subscription/cancel"

    try:
        checkout_url = service.create_checkout_session(
            user_id=user["id"],
            price_id=body.price_id,
            success_url=success_url,
            cancel_url=cancel_url,
        )
        return {"checkout_url": checkout_url}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/cancel")
async def cancel_subscription(
    user: dict = Depends(get_current_user)
):
    """
    Cancel subscription at end of billing period.

    User keeps access until paid period ends.
    No confirmation email needed - Stripe handles it.

    Returns:
    - success: Whether cancellation succeeded
    - ends_at: When access ends
    """
    service = SubscriptionService()
    result = service.cancel_subscription(user["id"])

    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error"))

    return result


@router.post("/refund")
async def request_refund(
    body: RefundRequest,
    user: dict = Depends(get_current_user)
):
    """
    Self-serve refund request.

    Only allowed:
    - Within 7 days of subscription start
    - Once per account (prevents abuse)

    Returns:
    - success: Whether refund was processed
    - refund_id: Stripe refund ID
    - amount: Amount refunded

    Subscription is canceled immediately on refund.
    """
    service = SubscriptionService()
    result = service.request_refund(user["id"], body.reason)

    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error"))

    return result


@router.get("/portal")
async def get_billing_portal(
    request: Request,
    user: dict = Depends(get_current_user)
):
    """
    Get Stripe Customer Portal URL.

    Portal allows users to:
    - Update payment method
    - View invoices
    - Download receipts
    - Cancel subscription

    All self-serve, no support needed.
    """
    service = SubscriptionService()

    return_url = str(request.base_url).rstrip("/") + "/settings"

    try:
        portal_url = service.get_billing_portal_url(user["id"], return_url)
        return {"portal_url": portal_url}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/prices")
async def get_prices():
    """
    Get available subscription prices.

    Returns the configured price IDs for frontend use.
    Simple: monthly or yearly, no tiers.
    """
    return {
        "monthly": {
            "price_id": os.environ.get("STRIPE_PRICE_MONTHLY"),
            "amount": 9,
            "currency": "usd",
            "interval": "month",
        },
        "yearly": {
            "price_id": os.environ.get("STRIPE_PRICE_YEARLY"),
            "amount": 79,
            "currency": "usd",
            "interval": "year",
        },
    }
