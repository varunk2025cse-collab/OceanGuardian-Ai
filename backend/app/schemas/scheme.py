from pydantic import BaseModel


class GovtSchemeOut(BaseModel):
    id: int
    title: str
    category: str
    region: str
    description: str
    eligibility: str
    how_to_apply: str
    contact_info: str | None

    model_config = {"from_attributes": True}
