from datetime import datetime, timedelta
from app.database import Base, engine, SessionLocal
from app.models import Patient, Offer, PatientOffer
from app.qr_service import new_token, new_uid, expiry_for, generate_qr

Base.metadata.create_all(bind=engine)
db = SessionLocal()
try:
    crown = db.query(Offer).filter(Offer.name == "Free In-House Zirconia Crown").first()
    aligner = db.query(Offer).filter(Offer.name == "Free In-House Aligner Scan").first()
    samples = [("Rahul Sharma", "9800000001", crown), ("Amit Kumar", "9800000002", aligner), ("Neha Singh", "9800000003", crown)]
    for name, mobile, offer in samples:
        p = Patient(patient_uid=new_uid("PAT"), full_name=name, mobile=mobile, city="Test City", campaign_name="DEVELOPMENT TEST DATA", created_at=datetime.utcnow())
        db.add(p); db.flush()
        c = PatientOffer(coupon_uid=new_uid("SRD"), patient_id=p.id, offer_id=offer.id, secure_token=new_token(), created_at=datetime.utcnow(), expires_at=expiry_for(datetime.utcnow()), status="ACTIVE")
        db.add(c); db.flush(); generate_qr(c.secure_token, c.coupon_uid)
    db.commit()
    print("Development seed complete: Rahul Sharma, Amit Kumar, Neha Singh")
finally:
    db.close()
