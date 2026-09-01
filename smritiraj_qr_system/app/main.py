from pathlib import Path
from fastapi import FastAPI
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
from .database import Base, engine, SessionLocal
from .models import Offer
from .config import SESSION_MAX_AGE_SECONDS, SESSION_HTTPS_ONLY, SESSION_SECRET_KEY, validate_security_config

app = FastAPI(title="Smriti Raj Dentistry - QR Offer Management System")
app.add_middleware(
    SessionMiddleware,
    secret_key=SESSION_SECRET_KEY,
    session_cookie="srd_clinic_session",
    max_age=SESSION_MAX_AGE_SECONDS,
    same_site="lax",
    https_only=SESSION_HTTPS_ONLY,
)

templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))
app.state.templates = templates
app.state.db = SessionLocal

from .routes import auth, dashboard, patients, coupons, validation
app.include_router(auth.router)
app.include_router(dashboard.router)
app.include_router(patients.router)
app.include_router(coupons.router)
app.include_router(validation.router)

@app.on_event("startup")
def startup():
    validate_security_config()
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        defaults = [
            ("Free In-House Zirconia Crown", "Complimentary in-house zirconia crown campaign offer."),
            ("Free In-House Aligner Scan", "Complimentary in-house aligner scan campaign offer."),
        ]
        for name, description in defaults:
            if not db.query(Offer).filter(Offer.name == name).first():
                db.add(Offer(name=name, description=description))
        db.commit()
    finally:
        db.close()
