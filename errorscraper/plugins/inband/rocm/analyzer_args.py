from pydantic import BaseModel, Field, field_validator


class RocmAnalyzerArgs(BaseModel):
    exp_rocm: str | list = Field(default_factory=list)

    @field_validator("exp_rocm", mode="before")
    @classmethod
    def validate_exp_rocm(cls, exp_rocm: str | list) -> list:
        """support str or list input for exp_rocm

        Args:
            exp_rocm (str | list): exp_rocm input

        Returns:
            list: exp_rocm list
        """
        if isinstance(exp_rocm, str):
            exp_rocm = [exp_rocm]

        return exp_rocm
