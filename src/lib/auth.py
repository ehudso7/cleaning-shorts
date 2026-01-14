"""
Authentication utilities.
Uses Supabase Auth - minimal, proven, zero custom code.
"""

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from ..db import get_supabase_client, get_admin_client
from ..models import SubscriptionStatus


security = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> dict:
    """
    Validate JWT and return current user.
    Uses Supabase Auth - no custom JWT handling.
    """
    client = get_supabase_client()

    try:
        # Verify the token with Supabase
        user = client.auth.get_user(credentials.credentials)

        if not user or not user.user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired token"
            )

        return {
            "id": user.user.id,
            "email": user.user.email,
        }

    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token"
        )


async def verify_subscription(
    user: dict = Depends(get_current_user)
) -> dict:
    """
    Verify user has an active subscription.
    Returns user if valid, raises 402 if subscription required.
    """
    client = get_admin_client()

    result = (
        client.table("users")
        .select("subscription_status")
        .eq("id", user["id"])
        .single()
        .execute()
    )

    if not result.data:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail="Subscription required"
        )

    status_value = result.data.get("subscription_status")
    allowed_statuses = [
        SubscriptionStatus.ACTIVE.value,
        SubscriptionStatus.TRIALING.value,
    ]

    if status_value not in allowed_statuses:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail="Active subscription required"
        )

    return user
