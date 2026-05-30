from pydantic import BaseModel, EmailStr, Field, model_validator
from datetime import date
from typing import Optional


class SendCodeRequest(BaseModel):
    email: EmailStr


class StudentRegisterRequest(BaseModel):
    first_name: str = Field(min_length=1, max_length=50)
    last_name: str = Field(min_length=1, max_length=50)
    email: EmailStr
    phone: Optional[str] = None
    password: str = Field(min_length=6)
    date_of_birth: date
    country_id: int
    state_id: int
    verification_code: str = Field(min_length=6, max_length=6)


class StudentLoginRequest(BaseModel):
    identifier: str  # email or phone
    password: str


class StudentRegistrationResponse(BaseModel):
    id: int
    first_name: str
    last_name: str
    email: str
    phone: Optional[str] = None
    country_id: int
    state_id: int

    model_config = {"from_attributes": True}


class StudentLoginResponse(BaseModel):
    id: int
    first_name: str
    last_name: str
    email: str
    phone: Optional[str] = None
