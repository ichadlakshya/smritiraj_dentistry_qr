from pydantic import BaseModel, EmailStr, Field, field_validator

class PatientCreate(BaseModel):
    full_name: str = Field(min_length=1, max_length=150)
    mobile: str = Field(min_length=5, max_length=30)
    email: EmailStr | None = None
    age: int | None = Field(default=None, ge=0, le=130)
    gender: str | None = None
    city: str | None = None
    doctor_name: str | None = None
    campaign_name: str | None = None
    offer_id: int

    @field_validator("mobile")
    @classmethod
    def clean_mobile(cls, v):
        value = "".join(ch for ch in v if ch.isdigit() or ch == "+")
        if len(value) < 5:
            raise ValueError("Enter a valid mobile number")
        return value
