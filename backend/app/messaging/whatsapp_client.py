"""HTTP client for the internal WhatsApp service (whatsapp/ folder)."""

import httpx

from app.core.config import settings


class WhatsAppError(Exception):
    def __init__(self, message: str, retriable: bool = True):
        super().__init__(message)
        self.retriable = retriable


def _client(timeout: float) -> httpx.Client:
    return httpx.Client(
        base_url=settings.whatsapp_url,
        headers={"x-internal-token": settings.whatsapp_token},
        timeout=timeout,
    )


def get_status(timeout: float = 5) -> dict | None:
    """{'connected': bool, 'state': str, 'qr': data-url|None, 'me': str|None}, or None if unreachable."""
    try:
        with _client(timeout) as c:
            r = c.get("/status")
            r.raise_for_status()
            return r.json()
    except httpx.HTTPError:
        return None


def send_text(phone: str, text: str) -> None:
    try:
        with _client(60) as c:
            r = c.post("/send", json={"phone": phone, "text": text})
    except httpx.HTTPError as e:
        raise WhatsAppError(f"WhatsApp service unreachable: {e}") from e
    if r.status_code == 200:
        return
    try:
        body = r.json()
    except ValueError:
        body = {}
    raise WhatsAppError(
        body.get("error") or f"HTTP {r.status_code}", retriable=body.get("retriable", True)
    )


def logout() -> bool:
    try:
        with _client(15) as c:
            return c.post("/logout").status_code == 200
    except httpx.HTTPError:
        return False
