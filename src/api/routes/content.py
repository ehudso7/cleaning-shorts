"""
Content delivery routes.
The core feature: get today's script + caption + CTA.

Design:
- One endpoint, one purpose
- Requires active subscription
- Returns deterministic content
- No configuration, no complexity
"""

from fastapi import APIRouter, Depends, HTTPException

from ...lib import ContentService, verify_subscription
from ...models import ContentResponse


router = APIRouter()


@router.get("/today", response_model=ContentResponse)
async def get_todays_content(
    user: dict = Depends(verify_subscription)
):
    """
    Get today's content for the authenticated user.

    Returns:
    - script: The video script (7-20 seconds)
    - caption: Short caption for the post
    - cta: Call to action text
    - delivery_date: Today's date
    - can_regenerate: Whether user can get a new one (always False)

    This is the only content endpoint needed.
    One content piece per day, no options, no complexity.
    """
    try:
        service = ContentService()
        return service.generate_daily_content(user["id"])
    except ValueError as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats")
async def get_content_stats(
    user: dict = Depends(verify_subscription)
):
    """
    Get stats about content consumption.

    Returns:
    - service_type: User's selected service type
    - total_templates: Total templates available
    - delivered: How many they've seen
    - remaining: How many left before reset

    Optional endpoint - helps users understand their progress.
    """
    service = ContentService()
    return service.get_delivery_stats(user["id"])
