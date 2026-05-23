from pydantic import BaseModel, ConfigDict


class ExamResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    exam_name: str
    exam_year: int
    description: str | None
    subject_id: int


class SubjectInExamResponse(BaseModel):
    """Distinct subject available within an exam (derived from blueprints → topics)."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str


class TopicInExamResponse(BaseModel):
    """Topic available within a given exam+subject, with blueprint metadata."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    topic_name: str
    expected_questions: int | None
    difficulty_level: str | None
