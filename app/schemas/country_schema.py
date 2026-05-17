from pydantic import BaseModel

class CountryResponse(BaseModel):
    id: int
    code: str
    name: str

 model_config = ConfigDict(
        from_attributes=True
 )