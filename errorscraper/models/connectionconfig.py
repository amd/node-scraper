from pydantic import BaseModel, Field


class ConnectionConfig(BaseModel):
    connection: dict[str, dict] = Field(default_factory=dict)
