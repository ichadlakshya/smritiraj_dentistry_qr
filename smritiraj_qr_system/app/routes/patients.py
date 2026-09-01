from datetime import datetime, timedelta
import logging
from fastapi import APIRouter, Depends, Request, Form, Query
from fastapi.responses import RedirectResponse
from pydantic import ValidationError
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError
from ..auth import require_auth
from ..models import Patient, PatientOffer, Offer, DeliveryLog, AuditLog
from ..schemas import PatientCreate
from ..qr_service import new_uid, expiry_for, generate_qr, token_for, token_hash
from ..audit_service import audit
from ..security import require_csrf

router = APIRouter()
logger = logging.getLogger(__name__)
CONSENT_VERSION = "2026-09-02"

def sunday_for(moment: datetime):
    return (moment - timedelta(days=(moment.weekday() + 1) % 7)).date()

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
    consent_given: bool = Form(False),
    _csrf: None = Depends(require_csrf),
):
    guard = require_auth(request)
    if guard: return guard
    db = request.app.state.db()
    try:
        try:
            form = PatientCreate(
                full_name=full_name,
                mobile=mobile,
                email=email or None,
                age=age or None,
                gender=gender or None,
                city=city or None,
                doctor_name=doctor_name or None,
                campaign_name=campaign_name or None,
                offer_id=offer_id,
                consent_given=consent_given,
            )
        except ValidationError as exc:
            first_error = exc.errors(include_url=False)[0]
            field = str(first_error.get("loc", ["field"])[-1]).replace("_", " ").title()
            raise ValueError(f"{field}: {first_error['msg']}") from None
        offer = db.get(Offer, form.offer_id)
        if not offer:
            raise ValueError("Please select a valid offer.")
        if not form.consent_given:
            raise ValueError("Patient consent is required before registration.")
        now = datetime.utcnow()
        registration_week = sunday_for(now)
        duplicate = db.query(Patient).filter(
            Patient.mobile == form.mobile,
            Patient.registration_week == registration_week,
        ).first()
        if duplicate:
            raise ValueError("This mobile number is already registered for the current Sunday-to-Saturday campaign week.")
        patient = Patient(
            patient_uid=new_uid("PAT"),
            full_name=form.full_name,
            mobile=form.mobile,
            email=str(form.email) if form.email else None,
            age=form.age,
            gender=form.gender,
            city=form.city,
            doctor_name=form.doctor_name,
            campaign_name=form.campaign_name,
            registration_week=registration_week,
            consent_given=True,
            consent_version=CONSENT_VERSION,
            consented_at=now,
            created_at=now,
        )
        db.add(patient)
        db.flush()
        coupon_uid = new_uid("SRD")
        token = token_for(coupon_uid)
        coupon = PatientOffer(
            coupon_uid=coupon_uid,
            patient_id=patient.id,
            offer_id=offer.id,
            secure_token_hash=token_hash(token),
            created_at=now,
            expires_at=expiry_for(now),
            status="ACTIVE",
        )
        db.add(coupon)
        db.flush()
        generate_qr(token, coupon.coupon_uid)
        audit(db, request.session.get("user", "admin"), "PATIENT_REGISTERED", coupon.id, patient.id, {
            "offer": offer.name, "registration_week": str(registration_week), "consent_version": CONSENT_VERSION
        })
        audit(db, "admin", "QR_GENERATED", coupon.id, patient.id)
        db.commit()
        return RedirectResponse(f"/patients/{patient.id}", status_code=303)
    except (ValueError, IntegrityError) as exc:
        db.rollback()
        offers = db.query(Offer).order_by(Offer.id).all()
        message = str(exc) if isinstance(exc, ValueError) else "This mobile number is already registered for the current campaign week."
        return request.app.state.templates.TemplateResponse("register.html", {"request": request, "offers": offers, "error": message}, status_code=422)
    except Exception:
        logger.exception("Patient registration failed")
        db.rollback()
        offers = db.query(Offer).order_by(Offer.id).all()
        return request.app.state.templates.TemplateResponse("register.html", {"request": request, "offers": offers, "error": "Registration could not be completed. Please try again."}, status_code=500)
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
        coupon = max(patient.offers, key=lambda item: item.created_at) if patient.offers else None
        events = db.query(AuditLog).filter(AuditLog.patient_id == patient.id).order_by(AuditLog.timestamp.desc()).all()
        return request.app.state.templates.TemplateResponse("patient_detail.html", {"request": request, "patient": patient, "coupon": coupon, "events": events})
    finally:
        db.close()

@router.post("/patients/{patient_id}/cancel")
def cancel_coupon(
    request: Request,
    patient_id: int,
    reason: str = Form(..., min_length=3, max_length=255),
    _csrf: None = Depends(require_csrf),
):
    guard = require_auth(request)
    if guard: return guard
    db = request.app.state.db()
    try:
        patient = db.get(Patient, patient_id)
        if not patient or not patient.offers:
            return RedirectResponse("/patients", status_code=303)
        coupon = max(patient.offers, key=lambda item: item.created_at)
        if coupon.status != "ACTIVE":
            return RedirectResponse(f"/patients/{patient_id}?message=Only active offers can be cancelled", status_code=303)
        now = datetime.utcnow()
        coupon.status = "CANCELLED"
        coupon.cancelled_at = now
        coupon.cancelled_by = request.session.get("user", "admin")
        coupon.cancellation_reason = " ".join(reason.split())
        audit(db, coupon.cancelled_by, "QR_CANCELLED", coupon.id, patient.id, {"reason": coupon.cancellation_reason})
        db.commit()
        return RedirectResponse(f"/patients/{patient_id}?message=Offer cancelled", status_code=303)
    finally:
        db.close()

@router.post("/patients/{patient_id}/delivery/email")
def send_email(request: Request, patient_id: int, _csrf: None = Depends(require_csrf)):
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
def whatsapp(request: Request, patient_id: int, _csrf: None = Depends(require_csrf)):
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
