from pydantic import BaseModel, ConfigDict


class ProfileRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    display_name: str
    avatar_color: str
    max_cast: int
