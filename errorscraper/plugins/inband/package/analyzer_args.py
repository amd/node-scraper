from pydantic import BaseModel, Field


class PackageAnalyzerArgs(BaseModel):
    exp_package_ver: dict[str, str | None] = Field(default_factory=dict)
    regex_match: bool = True
