"""
Content delivery service.
Core logic for deterministic, support-free content delivery.

Key design:
- No AI at runtime
- Pre-generated templates only
- One delivery per user per day
- No duplicates until library is exhausted
- Automatic rotation through entire library
"""

from datetime import datetime, date
from typing import Optional
import pytz

from ..models import ServiceType, ContentResponse
from ..db import get_admin_client


class ContentService:
    """Handles all content delivery logic."""

    def __init__(self):
        self.client = get_admin_client()

    def get_user_timezone(self, user_id: str) -> str:
        """Get user's configured timezone."""
        result = self.client.table("profiles").select("timezone").eq("user_id", user_id).single().execute()
        return result.data.get("timezone", "America/New_York") if result.data else "America/New_York"

    def get_user_service_type(self, user_id: str) -> ServiceType:
        """Get user's selected service type."""
        result = self.client.table("profiles").select("service_type").eq("user_id", user_id).single().execute()
        service = result.data.get("service_type", "deep_clean") if result.data else "deep_clean"
        return ServiceType(service)

    def get_today_date(self, timezone: str) -> date:
        """Get today's date in user's timezone."""
        tz = pytz.timezone(timezone)
        return datetime.now(tz).date()

    def get_todays_delivery(self, user_id: str) -> Optional[ContentResponse]:
        """
        Get today's content delivery for a user.
        Returns existing delivery if already generated, None otherwise.
        """
        timezone = self.get_user_timezone(user_id)
        today = self.get_today_date(timezone)

        # Check for existing delivery today
        result = (
            self.client.table("daily_deliveries")
            .select("template_id, delivered_at")
            .eq("user_id", user_id)
            .eq("delivery_date", today.isoformat())
            .single()
            .execute()
        )

        if not result.data:
            return None

        # Get the template content
        template = (
            self.client.table("content_templates")
            .select("script, caption, cta")
            .eq("id", result.data["template_id"])
            .single()
            .execute()
        )

        if not template.data:
            return None

        return ContentResponse(
            script=template.data["script"],
            caption=template.data["caption"],
            cta=template.data["cta"],
            delivery_date=today.isoformat(),
            can_regenerate=False,
        )

    def generate_daily_content(self, user_id: str) -> ContentResponse:
        """
        Generate or return today's content for a user.

        Logic:
        1. Check if content already delivered today -> return it
        2. Get user's service type
        3. Find unused template for that service type
        4. If all templates used, reset and start over
        5. Record delivery and return content
        """
        # Check for existing delivery
        existing = self.get_todays_delivery(user_id)
        if existing:
            return existing

        timezone = self.get_user_timezone(user_id)
        today = self.get_today_date(timezone)
        service_type = self.get_user_service_type(user_id)

        # Get next unused template
        template = self._get_next_template(user_id, service_type)

        if not template:
            # All templates used - reset and try again
            self._reset_delivery_history(user_id, service_type)
            template = self._get_next_template(user_id, service_type)

        if not template:
            # Fallback - should never happen if library has content
            raise ValueError("No content templates available")

        # Record the delivery
        self.client.table("daily_deliveries").insert({
            "user_id": user_id,
            "template_id": template["id"],
            "delivery_date": today.isoformat(),
        }).execute()

        return ContentResponse(
            script=template["script"],
            caption=template["caption"],
            cta=template["cta"],
            delivery_date=today.isoformat(),
            can_regenerate=False,
        )

    def _get_next_template(self, user_id: str, service_type: ServiceType) -> Optional[dict]:
        """
        Get a random template the user hasn't seen yet.
        Uses subquery to exclude already-delivered templates.
        """
        # Get IDs of templates already delivered to this user
        delivered = (
            self.client.table("daily_deliveries")
            .select("template_id")
            .eq("user_id", user_id)
            .execute()
        )
        delivered_ids = [d["template_id"] for d in delivered.data] if delivered.data else []

        # Build query for unused templates
        query = (
            self.client.table("content_templates")
            .select("*")
            .eq("service_type", service_type.value)
            .eq("is_active", True)
        )

        # Exclude already delivered
        if delivered_ids:
            query = query.not_.in_("id", delivered_ids)

        # Get one random template
        result = query.limit(1).execute()

        return result.data[0] if result.data else None

    def _reset_delivery_history(self, user_id: str, service_type: ServiceType) -> None:
        """
        Clear delivery history for a service type.
        Called when user has seen all templates.

        Note: We only delete deliveries for the current service type,
        so switching services doesn't lose history.
        """
        # Get all template IDs for this service type
        templates = (
            self.client.table("content_templates")
            .select("id")
            .eq("service_type", service_type.value)
            .execute()
        )
        template_ids = [t["id"] for t in templates.data] if templates.data else []

        if template_ids:
            # Delete old deliveries for these templates
            self.client.table("daily_deliveries").delete().eq("user_id", user_id).in_("template_id", template_ids).execute()

    def get_delivery_stats(self, user_id: str) -> dict:
        """Get stats about user's content consumption."""
        service_type = self.get_user_service_type(user_id)

        # Total templates available
        total = (
            self.client.table("content_templates")
            .select("id", count="exact")
            .eq("service_type", service_type.value)
            .eq("is_active", True)
            .execute()
        )

        # Templates already delivered
        delivered = (
            self.client.table("daily_deliveries")
            .select("id", count="exact")
            .eq("user_id", user_id)
            .execute()
        )

        total_count = total.count if total.count else 0
        delivered_count = delivered.count if delivered.count else 0

        return {
            "service_type": service_type.value,
            "total_templates": total_count,
            "delivered": delivered_count,
            "remaining": max(0, total_count - delivered_count),
        }
