from fastapi import APIRouter, Request
from sqlalchemy import func
from ..auth import require_auth
from ..models import Patient, PatientOffer, Offer

router = APIRouter()

@router.get("/")
def dashboard(request: Request):
    guard = require_auth(request)
    if guard: return guard
    db = request.app.state.db()
    try:
        total = db.query(func.count(Patient.id)).scalar() or 0
        active = db.query(func.count(PatientOffer.id)).filter(PatientOffer.status == "ACTIVE").scalar() or 0
        redeemed = db.query(func.count(PatientOffer.id)).filter(PatientOffer.status == "REDEEMED").scalar() or 0
        expired = db.query(func.count(PatientOffer.id)).filter(PatientOffer.status == "EXPIRED").scalar() or 0
        recent = db.query(PatientOffer).order_by(PatientOffer.created_at.desc()).limit(8).all()
        offers = db.query(Offer).all()
        stats = []
        for offer in offers:
            stats.append({
                "name": offer.name,
                "total": db.query(func.count(PatientOffer.id)).filter(PatientOffer.offer_id == offer.id).scalar() or 0,
                "active": db.query(func.count(PatientOffer.id)).filter(PatientOffer.offer_id == offer.id, PatientOffer.status == "ACTIVE").scalar() or 0,
                "redeemed": db.query(func.count(PatientOffer.id)).filter(PatientOffer.offer_id == offer.id, PatientOffer.status == "REDEEMED").scalar() or 0,
            })
        return request.app.state.templates.TemplateResponse("dashboard.html", {
            "request": request, "total": total, "active": active,
            "redeemed": redeemed, "expired": expired, "recent": recent, "stats": stats
        })
    finally:
        db.close()
