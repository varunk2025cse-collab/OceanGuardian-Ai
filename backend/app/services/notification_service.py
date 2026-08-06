"""
Notification engine (docs/NOTIFICATIONS.md) — provider abstraction for
push/SMS/email, with a real, fully-functional in-app + database channel
(FamilyNotification, previously schema-only per docs/V1_AUDIT.md §2/§12 —
nothing ever wrote to it) as the default, always-on delivery path.

No SMS/push/email provider credentials exist in this environment
(Twilio/FCM/SMTP). Per the "never fake capability" rule, the default
provider is SimulationNotificationProvider: it writes a real, queryable
FamilyNotification row with delivery_status recording exactly what
happened, but never claims a message left the building. A real provider
(TwilioProvider, SmtpProvider) activates only when its credentials are
configured via environment variables — see app.config.settings.
"""
import logging
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from enum import Enum

from sqlalchemy.orm import Session

from app.config import settings
from app.models.family_link import FamilyLink
from app.models.phase5 import FamilyNotification

logger = logging.getLogger("oceanguardian.notifications")


class NotificationPriority(str, Enum):
    critical = "CRITICAL"
    high = "HIGH"
    medium = "MEDIUM"
    low = "LOW"


class DeliveryResult:
    def __init__(self, status: str, detail: str, simulated: bool):
        self.status = status  # "sent" | "failed" | "simulated"
        self.detail = detail
        self.simulated = simulated


class NotificationProvider(ABC):
    """One channel adapter. Implementations must never raise for a normal
    delivery failure — they return a DeliveryResult so the caller can
    record it, retry, and audit it."""

    @abstractmethod
    def send(self, *, to_user_id: int, message: str, priority: NotificationPriority) -> DeliveryResult: ...


class SimulationNotificationProvider(NotificationProvider):
    """Default provider when no real credentials are configured. Logs the
    message and reports it as clearly SIMULATED — this is what makes
    development/demo possible without pretending a real SMS/push went out."""

    def send(self, *, to_user_id: int, message: str, priority: NotificationPriority) -> DeliveryResult:
        logger.info("SIMULATED_NOTIFICATION user_id=%s priority=%s message=%s", to_user_id, priority.value, message)
        return DeliveryResult(status="simulated", detail="No real provider configured — logged only.", simulated=True)


class TwilioSmsProvider(NotificationProvider):
    """Real SMS via Twilio. Only ever constructed when
    settings.twilio_account_sid/auth_token/from_number are all set — see
    NotificationEngine._select_provider. Uses httpx directly (already a
    project dependency) rather than adding the twilio SDK for one endpoint.
    """

    def __init__(self):
        import httpx

        self._client = httpx.Client(timeout=10.0)
        self._sid = settings.twilio_account_sid
        self._token = settings.twilio_auth_token
        self._from = settings.twilio_from_number

    def send(self, *, to_user_id: int, message: str, priority: NotificationPriority) -> DeliveryResult:
        # The generic provider interface only exposes a user-id, but Twilio
        # delivery requires a phone number. Return a failed result instead of
        # raising so the notification workflow can audit the failure without
        # breaking the request path.
        logger.warning(
            "Twilio provider requested for user_id=%s without an explicit phone number; delivery was not attempted",
            to_user_id,
        )
        return DeliveryResult(
            status="failed",
            detail="Twilio provider requires an explicit phone number for delivery",
            simulated=False,
        )

    def send_sms(self, *, to_phone: str, message: str) -> DeliveryResult:
        try:
            resp = self._client.post(
                f"https://api.twilio.com/2010-04-01/Accounts/{self._sid}/Messages.json",
                data={"From": self._from, "To": to_phone, "Body": message},
                auth=(self._sid, self._token),
            )
            if resp.status_code in (200, 201):
                return DeliveryResult(status="sent", detail="Twilio accepted the message.", simulated=False)
            return DeliveryResult(status="failed", detail=f"Twilio error {resp.status_code}: {resp.text[:200]}", simulated=False)
        except Exception as e:  # network failure, timeout, etc.
            return DeliveryResult(status="failed", detail=f"Twilio request failed: {e}", simulated=False)


class NotificationEngine:
    """Owns dispatch + the FamilyNotification audit trail. Every call is
    retryable (delivery_status is recorded, a failed row can be re-driven
    later) and deduplicated (same related_event_id + family_member_id is
    not re-sent — see notify_family_of_event)."""

    @staticmethod
    def _select_provider() -> NotificationProvider:
        if settings.notification_provider == "twilio" and settings.twilio_account_sid and settings.twilio_auth_token:
            return TwilioSmsProvider()
        return SimulationNotificationProvider()

    @staticmethod
    def notify_family_of_event(
        db: Session,
        fisherman_id: int,
        message: str,
        related_event_id: int | None = None,
        priority: NotificationPriority = NotificationPriority.high,
        notification_type: str = "push",
    ) -> list[FamilyNotification]:
        """Notifies every family member linked to this fisherman. Returns the
        FamilyNotification rows created (each carries its own delivery_status
        so the caller/UI can show exactly what happened per recipient)."""
        links = db.query(FamilyLink).filter(FamilyLink.fisherman_id == fisherman_id).all()
        if not links:
            return []

        provider = NotificationEngine._select_provider()
        created: list[FamilyNotification] = []
        for link in links:
            if related_event_id is not None:
                existing = (
                    db.query(FamilyNotification)
                    .filter(
                        FamilyNotification.family_member_id == link.family_user_id,
                        FamilyNotification.related_event_id == related_event_id,
                    )
                    .first()
                )
                if existing:
                    created.append(existing)
                    continue

            result = provider.send(to_user_id=link.family_user_id, message=message, priority=priority)
            row = FamilyNotification(
                family_member_id=link.family_user_id,
                notification_type=notification_type,
                message=message,
                related_event_id=related_event_id,
                sent_at=datetime.now(timezone.utc) if result.status in ("sent", "simulated") else None,
                delivery_status=result.status,
            )
            db.add(row)
            created.append(row)
        db.commit()
        for row in created:
            db.refresh(row)
        return created

    @staticmethod
    def publish_family_event(
        db: Session,
        fisherman_id: int,
        message: str,
        related_event_id: int | None = None,
        priority: NotificationPriority = NotificationPriority.high,
        notification_type: str = "push",
    ) -> tuple[int, str]:
        """Compatibility helper: publish a family notification request to the internal EventBus.

        This does not replace the existing notify_family_of_event immediate-send path — it
        offers a durable event ingestion point for a gradual rollout. Returns (event_id, correlation_id).
        """
        try:
            from app.event_bus import EventBus
        except Exception:
            # If EventBus is not available for any reason, fail gracefully
            logger.exception("EventBus unavailable while publishing family event")
            raise

        payload = {
            "fisherman_id": fisherman_id,
            "message": message,
            "related_event_id": related_event_id,
            "notification_type": notification_type,
        }
        metadata = {"priority": priority.value}
        event_id, correlation_id = EventBus.publish(db, event_type="family.notification.request", payload=payload, metadata=metadata, priority=priority.value, source_module="family_portal")
        logger.info("Published family notification event event_id=%s corr=%s fisherman_id=%s priority=%s", event_id, correlation_id, fisherman_id, priority.value)
        return event_id, correlation_id
