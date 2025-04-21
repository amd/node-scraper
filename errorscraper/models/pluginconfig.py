from pydantic import BaseModel, Field


class PluginConfig(BaseModel):

    global_args: dict = Field(default_factory=dict)
    plugins: dict[str, dict | BaseModel] = Field(default_factory=dict)
