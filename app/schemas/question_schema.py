from pydantic import BaseModel, ConfigDict

class QuestionCreate(BaseModel):
    text: str
    country_id: int
    exam: str
    subject: str


    model_config = ConfigDict(
        from_attributes=True
    )

class QuestionRead(BaseModel):
    id: int
    text: str
    country_id: int

    model_config = ConfigDict(
        from_attributes=True
    )