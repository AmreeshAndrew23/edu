from pydantic import BaseModel, ConfigDict


class StateResponse(BaseModel):
    id: int
    code: str
    name: str
    country_id: int

    model_config = ConfigDict(
        from_attributes=True
    )