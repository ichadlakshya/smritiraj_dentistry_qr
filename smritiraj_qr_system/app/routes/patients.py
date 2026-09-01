from datetime import datetime
from fastapi import APIRouter, Request, Form, Query
from fastapi.responses import RedirectResponse
from sqlalchemy import or_
from ..auth import require_auth
from ..models import Patient, PatientOffer, Offer, DeliveryLog
from ..schemas import PatientCreate
from ..qr_service import new_token, new_uid, expiry_for, generate_qr
from ..audit_service import audit

router = APIRouter()

@router.get("/patients")
def patients(request: Request, q: str = Query("", max_length=100), status: str = "", offer_id: int | None = None):
    guard = require_auth(request)
    if guard: return guard
    db = request.app.state.db()
    try:
        query = db.query(PatientOffer).join(Patient).join(Offer)
        if q:
            query = query.filter(or_(Patient.full_name.ilike(f"%{q}%"), Patient.mobile.ilike(f"%{q}%")))
        if status:
            query = query.filter(PatientOffer.status == status)
        if offer_id:
            query = query.filter(PatientOffer.offer_id == offer_id)
        rows = query.order_by(Patient.created_at.desc()).all()
        offers = db.query(Offer).all()
        return request.app.state.templates.TemplateResponse("patients.html", {
            "request": request, "rows": rows, "offers": offers, "q": q, "status": status, "offer_id": offer_id
        })
    finally:
        db.close()

@router.get("/patients/register")
def register_page(request: Request):
    guard = require_auth(request)
    if guard: return guard
    db = request.app.state.db()
    try:
        offers = db.query(Offer).order_by(Offer.id).all()
        return request.app.state.templates.TemplateResponse("register.html", {"request": request, "offers": offers, "error": None})
    finally:
        db.close()

@router.post("/patients/register")
def register_patient(
    request: Request,
    full_name: str = Form(...),
    mobile: str = Form(...),
    email: str = Form(""),
    age: str = Form(""),
    gender: str = Form(""),
    city: str = Form(""),
    doctor_name: str = Form(""),
    campaign_name: str = Form(""),
    offer_id: int = Form(...),
):
    guard = require_auth(request)
    if guard: return guard
    db = request.app.state.db()
    try:
        offer = db.get(Offer, offer_id)
        if not offer:
            raise ValueError("Please select a valid offer.")
        now = datetime.utcnow()
        patient = Patient(
            patient_uid=new_uid("PAT"),
            full_name=full_name.strip(),
            mobile=mobile.strip(),
            email=email.strip() or None,
            age=int(age) if age.strip() else None,
            gender=gender.strip() or None,
            city=city.strip() or None,
            doctor_name=doctor_name.strip() or None,
            campaign_name=campaign_name.strip() or None,
            created_at=now,
        )
        db.add(patient)
        db.flush()
        coupon = PatientOffer(
            coupon_uid=new_uid("SRD"),
            patient_id=patient.id,
            offer_id=offer.id,
            secure_token=new_token(),
            created_at=now,
            expires_at=expiry_for(now),
            status="ACTIVE",
        )
        db.add(coupon)
        db.flush()
        generate_qr(coupon.secure_token, coupon.coupon_uid)
        audit(db, "admin", "PATIENT_REGISTERED", coupon.id, patient.id, {"offer": offer.name})
        audit(db, "admin", "QR_GENERATED", coupon.id, patient.id)
        db.commit()
        return RedirectResponse(f"/patients/{patient.id}", status_code=303)
    except Exception as e:
        db.rollback()
        offers = db.query(Offer).order_by(Offer.id).all()
        return request.app.state.templates.TemplateResponse("register.html", {"request": request, "offers": offers, "error": str(e)})
    finally:
        db.close()

@router.get("/patients/{patient_id}")
def patient_detail(request: Request, patient_id: int):
    guard = require_auth(request)
    if guard: return guard
    db = request.app.state.db()
    try:
        patient = db.get(Patient, patient_id)
        if not patient:
            return RedirectResponse("/patients", status_code=303)
        coupon = patient.offers[0] if patient.offers else None
        return request.app.state.templates.TemplateResponse("patient_detail.html", {"request": request, "patient": patient, "coupon": coupon})
    finally:
        db.close()

@router.post("/patients/{patient_id}/delivery/email")
def send_email(request: Request, patient_id: int):
    guard = require_auth(request)
    if guard: return guard
    from ..email_service import prepare_email
    db = request.app.state.db()
    try:
        patient = db.get(Patient, patient_id)
        coupon = patient.offers[0]
        if not patient.email:
            return RedirectResponse(f"/patients/{patient_id}?message=No email address", status_code=303)
        from pathlib import Path
        from ..config import QR_DIR
        payload = prepare_email(patient, coupon, QR_DIR / f"{coupon.coupon_uid}.png")
        db.add(DeliveryLog(coupon_id=coupon.id, channel="EMAIL", status="PREPARED"))
        audit(db, "admin", "EMAIL_PREPARED", coupon.id, patient.id, {"recipient": patient.email})
        db.commit()
        return RedirectResponse(f"/patients/{patient_id}?message=Email prepared successfully", status_code=303)
    finally:
        db.close()

@router.post("/patients/{patient_id}/delivery/whatsapp")
def whatsapp(request: Request, patient_id: int):
    guard = require_auth(request)
    if guard: return guard
    from ..whatsapp_service import prepare_whatsapp
    db = request.app.state.db()
    try:
        patient = db.get(Patient, patient_id)
        coupon = patient.offers[0]
        link = prepare_whatsapp(patient, coupon)
        db.add(DeliveryLog(coupon_id=coupon.id, channel="WHATSAPP", status="PREPARED"))
        audit(db, "admin", "WHATSAPP_PREPARED", coupon.id, patient.id)
        db.commit()
        return RedirectResponse(link, status_code=303)
    finally:
        db.close()
