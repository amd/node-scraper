from pydantic import BaseModel, Field, field_validator


class KernelAnalyzerArgs(BaseModel):
    exp_kernel: str | list = Field(default_factory=list)
    regex_match: bool = False

    @field_validator("exp_kernel", mode="before")
    @classmethod
    def validate_exp_kernel(cls, exp_kernel: str | list) -> list:
        """support str or list input for exp_kernel

        Args:
            exp_kernel (str | list): exp kernel input

        Returns:
            list: exp kernel list
        """
        if isinstance(exp_kernel, str):
            exp_kernel = [exp_kernel]

        return exp_kernel
