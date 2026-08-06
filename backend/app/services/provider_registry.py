"""
Provider registry: returns a provider instance for a given channel.
For Sprint-1 we support only Simulation provider to avoid introducing credential dependencies.
"""
from typing import Any

from app.services.notification_service import SimulationNotificationProvider


class ProviderRegistry:
    @staticmethod
    def get_provider(channel: str) -> Any:
        # For now, always return simulation provider. Later, read settings and select Twilio/SMTP/FCM.
        return SimulationNotificationProvider()
