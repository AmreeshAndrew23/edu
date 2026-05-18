from pydantic import BaseModel, ConfigDict


class TopicCreate(BaseModel):
    name: str
    topic_name: str
    subject_id: int

    model_config = ConfigDict(
        from_attributes=True
    )