"""
Subscription management service.
Handles Stripe integration for billing.

Key design:
- Simple pricing: $9/month or $79/year
- Self-serve everything (no support tickets)
- Automatic refunds within 7-day window
- One refund per account (prevents abuse)
"""

import os
from datetime import datetime, timedelta
from typing import Optional
import stripe

from ..db import get_admin_client
from ..models import SubscriptionStatus


class SubscriptionService:
    """Handles all subscription and billing logic."""

    def __init__(self):
        self.client = get_admin_client()
        stripe.api_key = os.environ.get("STRIPE_SECRET_KEY")
        self.refund_window_days = int(os.environ.get("REFUND_WINDOW_DAYS", "7"))

    def get_subscription_status(self, user_id: str) -> dict:
        """Get current subscription status for a user."""
        result = (
            self.client.table("users")
            .select("subscription_status, subscription_started_at, subscription_ends_at, refund_used")
            .eq("id", user_id)
            .single()
            .execute()
        )

        if not result.data:
            return {"status": "none", "can_refund": False}

        data = result.data
        can_refund = self._can_request_refund(
            data.get("subscription_started_at"),
            data.get("refund_used", False)
        )

        return {
            "status": data.get("subscription_status", "none"),
            "started_at": data.get("subscription_started_at"),
            "ends_at": data.get("subscription_ends_at"),
            "can_refund": can_refund,
        }

    def _can_request_refund(self, started_at: Optional[str], refund_used: bool) -> bool:
        """Check if user is eligible for self-serve refund."""
        if refund_used:
            return False

        if not started_at:
            return False

        # Parse the timestamp
        if isinstance(started_at, str):
            start_date = datetime.fromisoformat(started_at.replace("Z", "+00:00"))
        else:
            start_date = started_at

        # Check if within refund window
        window_end = start_date + timedelta(days=self.refund_window_days)
        return datetime.now(start_date.tzinfo) <= window_end

    def create_checkout_session(self, user_id: str, price_id: str, success_url: str, cancel_url: str) -> str:
        """
        Create a Stripe Checkout session for subscription.
        Returns the checkout URL.
        """
        # Get or create Stripe customer
        user = (
            self.client.table("users")
            .select("email, stripe_customer_id")
            .eq("id", user_id)
            .single()
            .execute()
        )

        if not user.data:
            raise ValueError("User not found")

        customer_id = user.data.get("stripe_customer_id")

        if not customer_id:
            # Create Stripe customer
            customer = stripe.Customer.create(
                email=user.data["email"],
                metadata={"user_id": user_id}
            )
            customer_id = customer.id

            # Save customer ID
            self.client.table("users").update({
                "stripe_customer_id": customer_id
            }).eq("id", user_id).execute()

        # Create checkout session
        session = stripe.checkout.Session.create(
            customer=customer_id,
            mode="subscription",
            line_items=[{"price": price_id, "quantity": 1}],
            success_url=success_url,
            cancel_url=cancel_url,
            metadata={"user_id": user_id},
        )

        return session.url

    def handle_subscription_created(self, subscription: dict) -> None:
        """Handle Stripe webhook: subscription created."""
        customer_id = subscription.get("customer")
        subscription_id = subscription.get("id")

        # Find user by Stripe customer ID
        user = (
            self.client.table("users")
            .select("id")
            .eq("stripe_customer_id", customer_id)
            .single()
            .execute()
        )

        if not user.data:
            return

        # Update subscription status
        self.client.table("users").update({
            "subscription_status": "active",
            "stripe_subscription_id": subscription_id,
            "subscription_started_at": datetime.utcnow().isoformat(),
        }).eq("id", user.data["id"]).execute()

    def handle_subscription_updated(self, subscription: dict) -> None:
        """Handle Stripe webhook: subscription updated."""
        customer_id = subscription.get("customer")
        status = subscription.get("status")

        # Map Stripe status to our status
        status_map = {
            "active": "active",
            "past_due": "past_due",
            "canceled": "canceled",
            "unpaid": "past_due",
            "trialing": "trialing",
        }
        our_status = status_map.get(status, "canceled")

        user = (
            self.client.table("users")
            .select("id")
            .eq("stripe_customer_id", customer_id)
            .single()
            .execute()
        )

        if not user.data:
            return

        update_data = {"subscription_status": our_status}

        # If canceled, set end date
        if our_status == "canceled":
            cancel_at = subscription.get("cancel_at")
            if cancel_at:
                update_data["subscription_ends_at"] = datetime.fromtimestamp(cancel_at).isoformat()

        self.client.table("users").update(update_data).eq("id", user.data["id"]).execute()

    def handle_subscription_deleted(self, subscription: dict) -> None:
        """Handle Stripe webhook: subscription deleted."""
        customer_id = subscription.get("customer")

        user = (
            self.client.table("users")
            .select("id")
            .eq("stripe_customer_id", customer_id)
            .single()
            .execute()
        )

        if not user.data:
            return

        self.client.table("users").update({
            "subscription_status": "canceled",
            "subscription_ends_at": datetime.utcnow().isoformat(),
        }).eq("id", user.data["id"]).execute()

    def cancel_subscription(self, user_id: str) -> dict:
        """
        Cancel subscription at end of billing period.
        Self-serve, no support needed.
        """
        user = (
            self.client.table("users")
            .select("stripe_subscription_id")
            .eq("id", user_id)
            .single()
            .execute()
        )

        if not user.data or not user.data.get("stripe_subscription_id"):
            return {"success": False, "error": "No active subscription"}

        # Cancel at period end (they keep access until paid period ends)
        subscription = stripe.Subscription.modify(
            user.data["stripe_subscription_id"],
            cancel_at_period_end=True
        )

        return {
            "success": True,
            "ends_at": datetime.fromtimestamp(subscription.current_period_end).isoformat(),
        }

    def request_refund(self, user_id: str, reason: Optional[str] = None) -> dict:
        """
        Self-serve refund request.
        Only allowed within 7 days and if no previous refund.
        """
        user = (
            self.client.table("users")
            .select("stripe_customer_id, stripe_subscription_id, subscription_started_at, refund_used")
            .eq("id", user_id)
            .single()
            .execute()
        )

        if not user.data:
            return {"success": False, "error": "User not found"}

        # Check eligibility
        if not self._can_request_refund(
            user.data.get("subscription_started_at"),
            user.data.get("refund_used", False)
        ):
            return {"success": False, "error": "Not eligible for refund"}

        # Get the most recent charge
        charges = stripe.Charge.list(
            customer=user.data["stripe_customer_id"],
            limit=1
        )

        if not charges.data:
            return {"success": False, "error": "No charges found"}

        # Process refund
        charge = charges.data[0]
        refund = stripe.Refund.create(charge=charge.id)

        # Cancel subscription immediately
        if user.data.get("stripe_subscription_id"):
            stripe.Subscription.delete(user.data["stripe_subscription_id"])

        # Update user record
        self.client.table("users").update({
            "subscription_status": "canceled",
            "refund_used": True,
            "subscription_ends_at": datetime.utcnow().isoformat(),
        }).eq("id", user_id).execute()

        # Log the refund
        self.client.table("refund_log").insert({
            "user_id": user_id,
            "stripe_refund_id": refund.id,
            "amount_cents": refund.amount,
            "reason": reason,
        }).execute()

        return {
            "success": True,
            "refund_id": refund.id,
            "amount": refund.amount / 100,
        }

    def get_billing_portal_url(self, user_id: str, return_url: str) -> str:
        """
        Get Stripe Customer Portal URL for self-serve billing management.
        Users can update payment, view invoices, cancel - all without support.
        """
        user = (
            self.client.table("users")
            .select("stripe_customer_id")
            .eq("id", user_id)
            .single()
            .execute()
        )

        if not user.data or not user.data.get("stripe_customer_id"):
            raise ValueError("No billing account found")

        session = stripe.billing_portal.Session.create(
            customer=user.data["stripe_customer_id"],
            return_url=return_url,
        )

        return session.url
