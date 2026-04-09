"""Razorpay integration service — order creation and HMAC signature verification."""

import hashlib
import hmac
import httpx
import base64
from typing import Dict, Any

from app.core.config import settings

TIER_PRICES_PAISE = {
    "basic": 499900,      # Rs 4,999
    "standard": 999900,   # Rs 9,999
    "premium": 1999900,   # Rs 19,999
}


def get_tier_amount(tier: str) -> int:
    return TIER_PRICES_PAISE.get(tier.lower(), TIER_PRICES_PAISE["standard"])


async def create_razorpay_order(
    amount_paise: int,
    currency: str = "INR",
    receipt: str = "",
    notes: Dict[str, str] | None = None,
) -> Dict[str, Any]:
    """Create a Razorpay order via REST API."""
    key_id = getattr(settings, "razorpay_key_id", "")
    key_secret = getattr(settings, "razorpay_key_secret", "")

    if not key_id or not key_secret:
        # Return mock order for development
        import uuid
        mock_id = f"order_mock_{uuid.uuid4().hex[:16]}"
        return {
            "id": mock_id,
            "amount": amount_paise,
            "currency": currency,
            "status": "created",
        }

    credentials = base64.b64encode(f"{key_id}:{key_secret}".encode()).decode()
    payload = {
        "amount": amount_paise,
        "currency": currency,
        "receipt": receipt or "hirex_receipt",
        "notes": notes or {},
    }

    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://api.razorpay.com/v1/orders",
            json=payload,
            headers={"Authorization": f"Basic {credentials}"},
            timeout=10.0,
        )
        response.raise_for_status()
        return response.json()


def verify_razorpay_signature(order_id: str, payment_id: str, signature: str) -> bool:
    """Verify Razorpay payment signature using HMAC SHA256."""
    key_secret = getattr(settings, "razorpay_key_secret", "")

    if not key_secret:
        # Dev mode: accept mock payments
        return True

    message = f"{order_id}|{payment_id}"
    expected = hmac.new(
        key_secret.encode("utf-8"),
        message.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected, signature)
