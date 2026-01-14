"""
User management routes.
Minimal - just onboarding and profile updates.

No complex settings, no preferences bloat.
Just: service type + timezone.
"""

from fastapi import APIRouter, Depends, HTTPException

from ...lib import get_current_user
from ...db import get_admin_client
from ...models import OnboardingRequest, ServiceType


router = APIRouter()


@router.get("/profile")
async def get_profile(
    user: dict = Depends(get_current_user)
):
    """
    Get user profile.

    Returns:
    - service_type: Selected cleaning service type
    - timezone: User's timezone
    - onboarding_completed: Whether setup is done
    """
    client = get_admin_client()

    result = (
        client.table("profiles")
        .select("service_type, timezone, onboarding_completed")
        .eq("user_id", user["id"])
        .single()
        .execute()
    )

    if not result.data:
        # No profile yet - return defaults
        return {
            "service_type": ServiceType.DEEP_CLEAN.value,
            "timezone": "America/New_York",
            "onboarding_completed": False,
        }

    return result.data


@router.post("/onboard")
async def complete_onboarding(
    body: OnboardingRequest,
    user: dict = Depends(get_current_user)
):
    """
    Complete onboarding - set service type and timezone.

    Body:
    - service_type: deep_clean, airbnb, or move_out
    - timezone: IANA timezone (e.g., America/New_York)

    This is the only configuration needed.
    One choice, then they're ready to use the app.
    """
    client = get_admin_client()

    # Upsert profile
    client.table("profiles").upsert({
        "user_id": user["id"],
        "service_type": body.service_type.value,
        "timezone": body.timezone,
        "onboarding_completed": True,
    }).execute()

    return {
        "success": True,
        "service_type": body.service_type.value,
        "timezone": body.timezone,
    }


@router.put("/service-type")
async def update_service_type(
    body: dict,
    user: dict = Depends(get_current_user)
):
    """
    Update service type.

    Allowed values: deep_clean, airbnb, move_out

    Changing service type:
    - Immediately affects daily content
    - Does NOT reset delivery history
    - User can switch freely
    """
    service_type = body.get("service_type")

    if service_type not in [s.value for s in ServiceType]:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid service type. Must be one of: {[s.value for s in ServiceType]}"
        )

    client = get_admin_client()

    client.table("profiles").update({
        "service_type": service_type,
    }).eq("user_id", user["id"]).execute()

    return {"success": True, "service_type": service_type}


@router.put("/timezone")
async def update_timezone(
    body: dict,
    user: dict = Depends(get_current_user)
):
    """
    Update timezone.

    Affects when "today" rolls over for content delivery.
    """
    timezone = body.get("timezone")

    if not timezone:
        raise HTTPException(status_code=400, detail="Timezone required")

    # Basic validation - pytz will handle the rest
    try:
        import pytz
        pytz.timezone(timezone)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid timezone")

    client = get_admin_client()

    client.table("profiles").update({
        "timezone": timezone,
    }).eq("user_id", user["id"]).execute()

    return {"success": True, "timezone": timezone}
