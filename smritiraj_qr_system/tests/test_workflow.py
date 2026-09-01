from datetime import datetime, timedelta
from app.database import SessionLocal
from app.models import PatientOffer

def test_patient_registration_and_qr(client):
    r = client.post("/patients/register", data={
        "full_name":"Test Patient","mobile":"9999999999","email":"",
        "age":"30","gender":"Male","city":"Delhi","doctor_name":"","campaign_name":"Test",
        "offer_id":"1"
    }, follow_redirects=False)
    assert r.status_code == 303
    location = r.headers["location"]
    assert location.startswith("/patients/")
    db = SessionLocal()
    coupon = db.query(PatientOffer).first()
    assert coupon is not None
    assert coupon.secure_token.startswith("SRD-")
    assert coupon.expires_at - coupon.created_at == timedelta(days=10)
    assert coupon.status == "ACTIVE"
    db.close()

def test_valid_then_redeemed_then_second_attempt_fails(client):
    client.post("/patients/register", data={"full_name":"Double Use","mobile":"9999999998","offer_id":"1"})
    db = SessionLocal(); coupon = db.query(PatientOffer).first(); token = coupon.secure_token; cid = coupon.id; db.close()

    r = client.get(f"/validate?token={token}")
    assert "OFFER VALID" in r.text

    r = client.post(f"/redeem/{cid}", follow_redirects=True)
    assert "OFFER ALREADY USED" in r.text

    db = SessionLocal(); coupon = db.get(PatientOffer, cid); assert coupon.status == "REDEEMED"; db.close()

def test_invalid_token(client):
    r = client.get("/validate?token=SRD-NOT-REAL")
    assert "INVALID QR" in r.text

def test_different_offers_are_stored(client):
    client.post("/patients/register", data={"full_name":"Crown","mobile":"9999999991","offer_id":"1"})
    client.post("/patients/register", data={"full_name":"Aligner","mobile":"9999999992","offer_id":"2"})
    db = SessionLocal()
    rows = db.query(PatientOffer).order_by(PatientOffer.id).all()
    assert [x.offer_id for x in rows] == [1,2]
    assert rows[0].secure_token != rows[1].secure_token
    db.close()

def test_patient_search(client):
    client.post("/patients/register", data={"full_name":"Unique Search Person","mobile":"9999999990","offer_id":"1"})
    r = client.get("/patients?q=Unique+Search")
    assert "Unique Search Person" in r.text
