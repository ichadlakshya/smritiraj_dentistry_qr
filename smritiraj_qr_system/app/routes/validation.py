from datetime import datetime
from fastapi import APIRouter, Request, Form
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from ..auth import require_auth
from ..models import PatientOffer
from ..coupon_service import refresh_expiry, redeem_atomic
from ..audit_service import audit

router = APIRouter()

def find_coupon(db, token):
    return db.execute(select(PatientOffer).where(PatientOffer.secure_token == token.strip())).scalar_one_or_none()

@router.get("/validate")
def validate_page(request: Request, token: str = ""):
    guard = require_auth(request)
    if guard: return guard
    db = request.app.state.db()
    try:
        result = None
        if token:
            coupon = find_coupon(db, token)
            now = datetime.utcnow()
            if not coupon:
                result = {"kind": "INVALID", "message": "This QR/token is not registered in the Smriti Raj Dentistry system."}
            else:
                changed = refresh_expiry(coupon, now)
                if changed:
                    audit(db, "admin", "QR_EXPIRED", coupon.id, coupon.patient_id)
                    db.commit()
                if coupon.status == "REDEEMED":
                    result = {"kind": "REDEEMED", "coupon": coupon}
                elif coupon.status == "CANCELLED":
                    result = {"kind": "CANCELLED", "coupon": coupon}
                elif coupon.status == "EXPIRED":
                    result = {"kind": "EXPIRED", "coupon": coupon}
                else:
                    result = {"kind": "VALID", "coupon": coupon}
                audit(db, "admin", "QR_VALIDATED", coupon.id, coupon.patient_id, {"result": result["kind"]})
                db.commit()
        return request.app.state.templates.TemplateResponse("validate.html", {"request": request, "result": result, "token": token})
    finally:
        db.close()

@router.post("/validate")
def validate_submit(request: Request, token: str = Form(...)):
    return RedirectResponse(f"/validate?token={token.strip()}", status_code=303)

@router.post("/redeem/{coupon_id}")
def redeem(request: Request, coupon_id: int):
    guard = require_auth(request)
    if guard: return guard
    db = request.app.state.db()
    try:
        coupon = db.get(PatientOffer, coupon_id)
        if not coupon:
            return RedirectResponse("/validate", status_code=303)
        now = datetime.utcnow()
        ok = redeem_atomic(db, coupon.id, request.session.get("user", "admin"), now)
        if ok:
            # Atomic update succeeded. Audit in a separate transaction.
            db.add(__import__("app.models", fromlist=["AuditLog"]).AuditLog(
                user=request.session.get("user", "admin"),
                action="QR_REDEEMED",
                coupon_id=coupon.id,
                patient_id=coupon.patient_id,
            ))
            db.commit()
            return RedirectResponse(f"/validate?token={coupon.secure_token}", status_code=303)
        return RedirectResponse(f"/validate?token={coupon.secure_token}", status_code=303)
    finally:
        db.close()

