from pydantic import BaseModel, Field, field_validator


class BiosAnalyzerArgs(BaseModel):
    exp_bios_version: list[str] = Field(default_factory=list)
    regex_match: bool = False

    @field_validator("exp_bios_version", mode="before")
    @classmethod
    def validate_exp_bios_version(cls, exp_bios_version: str | list) -> list:
        """support str or list input for exp_bios_version

        Args:
            exp_bios_version (str | list): _description_

        Returns:
            list: _description_
        """
        if isinstance(exp_bios_version, str):
            exp_bios_version = [exp_bios_version]

        return exp_bios_version
