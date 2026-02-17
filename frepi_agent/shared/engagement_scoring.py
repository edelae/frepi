"""
Engagement Scoring Service - Calculates and updates engagement scores.

Shared across both Frepi Procurement and Frepi Finance agents.
The engagement score drives the drip question pacing.

Formula:
  score = (
      0.15 * onboarding_depth_signal +       # {0: 0.0, 5: 0.5, 10: 1.0}
      0.30 * drip_response_rate +             # answered / (answered + skipped)
      0.25 * correction_signal +              # min(corrections / 5, 1.0)
      0.15 * session_frequency_signal +       # min(sessions_30d / 10, 1.0)
      0.15 * reasoning_signal                 # with_reason / total_corrections
  )

Level thresholds:
  >= 0.65 → high    (2 drip questions/session, ask mid_tail products too)
  >= 0.35 → medium  (1 drip question/session, head products only)
  >= 0.10 → low     (0 drip, infer only)
  <  0.10 → dormant (0 drip, stop; re-engage after 14 days or next purchase)
"""

import logging
from typing import Optional

from frepi_agent.shared.supabase_client import get_supabase_client, Tables

logger = logging.getLogger(__name__)


def recalculate_engagement(restaurant_id: int) -> Optional[dict]:
    """
    Recalculate the engagement score and level for a restaurant.

    Args:
        restaurant_id: The restaurant ID

    Returns:
        Dict with updated score and level, or None if no profile exists
    """
    client = get_supabase_client()

    # Get current profile
    result = client.table(Tables.ENGAGEMENT_PROFILE).select(
        "*"
    ).eq("restaurant_id", restaurant_id).limit(1).execute()

    if not result.data:
        return None

    profile = result.data[0]

    # Calculate each signal

    # 1. Onboarding depth signal (0.15 weight)
    depth = profile.get("onboarding_depth", 0)
    depth_signal = {0: 0.0, 5: 0.5, 10: 1.0}.get(depth, 0.0)

    # 2. Drip response rate (0.30 weight)
    answered = profile.get("drip_questions_answered", 0)
    skipped = profile.get("drip_questions_skipped", 0)
    total_drip = answered + skipped
    drip_response_rate = answered / total_drip if total_drip > 0 else 0.0

    # 3. Correction signal (0.25 weight)
    corrections = profile.get("total_corrections", 0)
    correction_signal = min(corrections / 5.0, 1.0)

    # 4. Session frequency signal (0.15 weight)
    sessions_30d = profile.get("sessions_last_30d", 0)
    session_frequency_signal = min(sessions_30d / 10.0, 1.0)

    # 5. Reasoning signal (0.15 weight)
    with_reason = profile.get("corrections_with_reason", 0)
    reasoning_signal = with_reason / corrections if corrections > 0 else 0.0

    # Weighted sum
    score = round(
        0.15 * depth_signal
        + 0.30 * drip_response_rate
        + 0.25 * correction_signal
        + 0.15 * session_frequency_signal
        + 0.15 * reasoning_signal,
        2,
    )

    # Clamp to [0, 1]
    score = max(0.0, min(1.0, score))

    # Determine level and drip rate
    if score >= 0.65:
        level = "high"
        drip_per_session = 2
    elif score >= 0.35:
        level = "medium"
        drip_per_session = 1
    elif score >= 0.10:
        level = "low"
        drip_per_session = 0
    else:
        level = "dormant"
        drip_per_session = 0

    # Update profile
    client.table(Tables.ENGAGEMENT_PROFILE).update({
        "engagement_score": score,
        "engagement_level": level,
        "drip_questions_per_session": drip_per_session,
    }).eq("restaurant_id", restaurant_id).execute()

    logger.info(
        f"Engagement recalculated for restaurant {restaurant_id}: "
        f"score={score}, level={level}, drip={drip_per_session} "
        f"(depth={depth_signal:.2f}, drip_rate={drip_response_rate:.2f}, "
        f"corrections={correction_signal:.2f}, sessions={session_frequency_signal:.2f}, "
        f"reasoning={reasoning_signal:.2f})"
    )

    return {
        "score": score,
        "level": level,
        "drip_per_session": drip_per_session,
        "signals": {
            "depth": depth_signal,
            "drip_rate": drip_response_rate,
            "corrections": correction_signal,
            "session_frequency": session_frequency_signal,
            "reasoning": reasoning_signal,
        },
    }


def increment_session_count(restaurant_id: int):
    """
    Increment the session counter for engagement tracking.
    Call this at the start of each new session.
    """
    client = get_supabase_client()

    result = client.table(Tables.ENGAGEMENT_PROFILE).select(
        "sessions_last_30d"
    ).eq("restaurant_id", restaurant_id).limit(1).execute()

    if result.data:
        from datetime import datetime, timezone

        current = result.data[0].get("sessions_last_30d", 0)
        client.table(Tables.ENGAGEMENT_PROFILE).update({
            "sessions_last_30d": current + 1,
            "last_session_at": datetime.now(timezone.utc).isoformat(),
        }).eq("restaurant_id", restaurant_id).execute()
