"""
Data models for the Cleaning Shorts app.
Minimal by design - deterministic content, no ambiguity.
"""

from datetime import datetime, date
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field, EmailStr


class ServiceType(str, Enum):
    """The three service types for cleaning businesses."""
    DEEP_CLEAN = "deep_clean"
    AIRBNB = "airbnb"
    MOVE_OUT = "move_out"


class SubscriptionStatus(str, Enum):
    """Subscription states - simple, no edge cases."""
    ACTIVE = "active"
    CANCELED = "canceled"
    PAST_DUE = "past_due"
    TRIALING = "trialing"


class User(BaseModel):
    """Core user record - minimal fields."""
    id: str
    email: EmailStr
    created_at: datetime
    subscription_status: SubscriptionStatus = SubscriptionStatus.TRIALING
    stripe_customer_id: Optional[str] = None
    subscription_started_at: Optional[datetime] = None
    refund_used: bool = False


class UserProfile(BaseModel):
    """User preferences - just service type and timezone."""
    user_id: str
    service_type: ServiceType = ServiceType.DEEP_CLEAN
    timezone: str = "America/New_York"


class ContentTemplate(BaseModel):
    """
    Pre-generated content template.
    This is the core asset - no AI at runtime.
    """
    id: int
    service_type: ServiceType
    script: str = Field(..., description="7-20 second script with Hook/Visual/CTA")
    caption: str = Field(..., max_length=180, description="Short caption, 1 emoji max")
    cta: str = Field(default="DM 'CLEAN' for pricing & availability.")
    category: Optional[str] = None  # before_after, process, pricing, etc.
    is_active: bool = True


class DailyDelivery(BaseModel):
    """
    Tracks what content was delivered to each user each day.
    Prevents duplicates, enables deterministic delivery.
    """
    id: int
    user_id: str
    template_id: int
    delivered_at: datetime
    delivery_date: date  # The calendar date (in user's timezone)


class ContentResponse(BaseModel):
    """What the API returns to the user - clean, ready to use."""
    script: str
    caption: str
    cta: str
    delivery_date: str
    can_regenerate: bool = False


class SubscriptionRequest(BaseModel):
    """Request to create/manage subscription."""
    price_id: str  # monthly or yearly Stripe price


class RefundRequest(BaseModel):
    """Self-serve refund request."""
    reason: Optional[str] = None


class OnboardingRequest(BaseModel):
    """Initial setup - just service type and timezone."""
    service_type: ServiceType
    timezone: str = "America/New_York"
