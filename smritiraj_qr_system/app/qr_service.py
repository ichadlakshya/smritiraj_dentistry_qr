import secrets
from datetime import datetime, timedelta
from pathlib import Path
import qrcode
from .config import QR_DIR, PUBLIC_BASE_URL

def new_token() -> str:
    return "SRD-" + secrets.token_urlsafe(32)

def new_uid(prefix: str) -> str:
    return f"{prefix}-{secrets.token_hex(4).upper()}"

def expiry_for(created_at: datetime) -> datetime:
    return created_at + timedelta(days=10)

def qr_payload(token: str) -> str:
    # Only the opaque secure token is encoded. No patient information is embedded.
    return token

def generate_qr(token: str, coupon_uid: str) -> Path:
    img = qrcode.make(qr_payload(token))
    path = QR_DIR / f"{coupon_uid}.png"
    img.save(path)
    return path
