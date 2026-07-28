"""
SOS escalation logic, isolated from the route handler so it can grow
(push notifications, SMS-over-satellite, Coast Guard webhook, auto-escalation
timers) without bloating app/routers/sos.py.

For the MVP this synchronously logs what a production system would dispatch.
Swap `notify_emergency_contacts` for a real SMS/push provider integration
when one is selected (Stage 2+).
"""
import logging

from app.models.user import User
from app.models.sos import SOSAlert

logger = logging.getLogger("oceanguardian.sos")


def notify_emergency_contacts(user: User, alert: SOSAlert) -> None:
    """
    Fire-and-forget notification fan-out for a new SOS alert.

    MVP: structured log line a real notification worker can pick up from.
    Production: push to family app, SMS to emergency_contact_phone, and a
    webhook to the rescue/Coast Guard dashboard queue.
    """
    logger.warning(
        "SOS_TRIGGERED user_id=%s name=%s lat=%s lon=%s emergency_contact=%s",
        user.id,
        user.full_name,
        alert.latitude,
        alert.longitude,
        user.emergency_contact_phone,
    )
