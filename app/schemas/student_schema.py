from pydantic import BaseModel, EmailStr, Field
from datetime import date


class StudentRegisterRequest(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    email: EmailStr
    date_of_birth: date

    country_id: int
    state_id: int

class StudentRegistrationResponse(BaseModel):
    id: int
    name: str
    email: EmailStr
    date_of_birth: date
    country_id: int
    state_id: int

    class Config:
        orm_mode = True