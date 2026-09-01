import secrets
from fastapi import Request
from fastapi.responses import RedirectResponse
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from .config import CLINIC_PASSWORD_HASH, CLINIC_USERNAME, SESSION_VERSION

SESSION_USER = "admin"
password_hasher = PasswordHasher()

def verify_credentials(username: str, password: str) -> bool:
    username_ok = secrets.compare_digest(username.strip(), CLINIC_USERNAME)
    try:
        password_ok = password_hasher.verify(CLINIC_PASSWORD_HASH, password)
    except (InvalidHashError, VerificationError):
        password_ok = False
    return username_ok and password_ok

def is_authenticated(request: Request) -> bool:
    return (
        request.session.get("user") == SESSION_USER
        and request.session.get("session_version") == SESSION_VERSION
    )

def require_auth(request: Request):
    if not is_authenticated(request):
        return RedirectResponse("/login", status_code=303)
    return None
