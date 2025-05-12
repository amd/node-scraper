from pydantic import BaseModel, Field


class PluginConfig(BaseModel):

    global_args: dict = Field(default_factory=dict)
    plugins: dict[str, dict] = Field(default_factory=dict)
    result_collators: dict[str, dict] = Field(default_factory=dict)
