"""Email-verification delivery adapters."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from urllib.parse import urlencode

from app.core.config import Settings


logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class VerificationDelivery:
    email: str
    verification_url: str


class ConsoleEmailVerificationSender:
    """
    Local-development sender.

    The verification URL is written to backend logs. A production email
    provider will replace this adapter without changing application logic.
    """

    def __init__(self, settings: Settings) -> None:
        self._base_url = settings.email_verification_base_url

    async def send(
        self,
        *,
        email: str,
        raw_token: str,
    ) -> VerificationDelivery:
        query = urlencode({"token": raw_token})
        separator = (
            "&"
            if "?" in self._base_url
            else "?"
        )
        verification_url = (
            f"{self._base_url}{separator}{query}"
        )

        logger.warning(
            "EMAIL VERIFICATION (development only) | "
            "email=%s | url=%s",
            email,
            verification_url,
        )

        return VerificationDelivery(
            email=email,
            verification_url=verification_url,
        )
