"""
SOS escalation logic, isolated from the route handler so it can grow
(push notifications, SMS-over-satellite, Coast Guard webhook, auto-escalation
timers) without bloating app/routers/sos.py.

Production behavior:
  - Dispatches CRITICAL-priority notifications to every linked family member
    via the NotificationEngine (in-app + provider channels).
  - Dispatches an SMS to the fisherman's emergency contact phone when a real
    SMS provider (Twilio) is configured.
  - Records a structured audit log for every dispatch attempt.
  - Never raises: a notification failure must never turn a successful SOS
    trigger into a failed request (governing safety principle).
"""
import logging

from sqlalchemy.orm import Session

from app.models.user import User
from app.models.sos import SOSAlert
from app.services.notification_service import NotificationEngine, NotificationPriority

logger = logging.getLogger("oceanguardian.sos")


def notify_emergency_contacts(db: Session, user: User, alert: SOSAlert) -> None:
    """
    Fire-and-forget notification fan-out for a new SOS alert.

    Dispatches:
      1. CRITICAL-priority in-app notification to every linked family member
         (via NotificationEngine — writes FamilyNotification rows with
         delivery_status for auditability).
      2. SMS to the fisherman's emergency contact phone when a real SMS
         provider is configured (Twilio). Falls back to a clearly-labeled
         simulated delivery when no provider credentials exist.

    Every dispatch is isolated so one failing channel never blocks another,
    and a failure in any channel never raises to the caller — the SOS alert
    itself is already committed and safe.
    """
    # 1. Notify linked family members via the NotificationEngine.
    try:
        NotificationEngine.notify_family_of_event(
            db,
            fisherman_id=user.id,
            message=(
                f"🚨 SOS ALERT: {user.full_name} triggered an emergency "
                f"({alert.alert_type or 'MANUAL_SOS'}) at "
                f"{alert.latitude:.5f}, {alert.longitude:.5f}. "
                f"Please check on them immediately."
            ),
            related_event_id=alert.id,
            priority=NotificationPriority.critical,
            notification_type="sos_alert",
        )
        logger.info(
            "SOS family notification dispatched user_id=%s alert_id=%s",
            user.id,
            alert.id,
        )
    except Exception:
        logger.exception(
            "Failed to dispatch family notifications for SOS alert %s — alert itself is safe.",
            alert.id,
        )

    # 2. Dispatch SMS to the emergency contact when a real provider is configured.
    if user.emergency_contact_phone:
        try:
            from app.services.notification_service import NotificationEngine as NE
            from app.config import settings

            if settings.notification_provider == "twilio" and settings.twilio_account_sid:
                provider = NE._select_provider()
                if hasattr(provider, "send_sms"):
                    result = provider.send_sms(
                        to_phone=user.emergency_contact_phone,
                        message=(
                            f"🚨 SOS: {user.full_name} triggered an emergency at "
                            f"{alert.latitude:.5f}, {alert.longitude:.5f}. "
                            f"Please check on them immediately."
                        ),
                    )
                    logger.info(
                        "SOS SMS dispatch emergency_contact=%s status=%s detail=%s",
                        user.emergency_contact_phone,
                        result.status,
                        result.detail,
                    )
                else:
                    logger.warning(
                        "SMS provider does not support send_sms — emergency contact not notified via SMS",
                    )
            else:
                logger.info(
                    "SOS_SMS_SIMULATED emergency_contact=%s — no real SMS provider configured",
                    user.emergency_contact_phone,
                )
        except Exception:
            logger.exception(
                "Failed to dispatch SMS for SOS alert %s — alert itself is safe.",
                alert.id,
            )

    # 3. Structured audit log for operators/observability.
    logger.warning(
        "SOS_TRIGGERED user_id=%s name=%s lat=%s lon=%s emergency_contact=%s alert_id=%s",
        user.id,
        user.full_name,
        alert.latitude,
        alert.longitude,
        user.emergency_contact_phone,
        alert.id,
    )