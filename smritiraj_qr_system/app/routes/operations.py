from fastapi import APIRouter, Request

from ..auth import require_auth
from ..models import DeliveryLog, PatientOffer

router = APIRouter()

@router.get("/redemptions")
def redemptions(request: Request):
    guard = require_auth(request)
    if guard:
        return guard
    db = request.app.state.db()
    try:
        rows = db.query(PatientOffer).filter(PatientOffer.status == "REDEEMED").order_by(PatientOffer.redeemed_at.desc()).all()
        return request.app.state.templates.TemplateResponse("redemptions.html", {"request": request, "rows": rows})
    finally:
        db.close()

@router.get("/delivery")
def delivery(request: Request):
    guard = require_auth(request)
    if guard:
        return guard
    db = request.app.state.db()
    try:
        rows = db.query(DeliveryLog, PatientOffer).join(PatientOffer, DeliveryLog.coupon_id == PatientOffer.id).order_by(DeliveryLog.sent_at.desc()).all()
        return request.app.state.templates.TemplateResponse("delivery.html", {"request": request, "rows": rows})
    finally:
        db.close()
