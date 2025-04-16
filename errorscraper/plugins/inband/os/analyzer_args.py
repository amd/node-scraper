from pydantic import BaseModel, Field, field_validator


class OsAnalyzerArgs(BaseModel):
    exp_os: str | list = Field(default_factory=list)
    exact_match: bool = True

    @field_validator("exp_os", mode="before")
    @classmethod
    def validate_exp_os(cls, exp_os: str | list) -> list:
        """support str or list input for exp_os

        Args:
            exp_os (str | list): exp_os input

        Returns:
            list: exp_os list
        """
        if isinstance(exp_os, str):
            exp_os = [exp_os]

        return exp_os
