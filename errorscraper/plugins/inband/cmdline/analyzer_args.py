from pydantic import BaseModel, Field, field_validator


class CmdlineAnalyzerArgs(BaseModel):
    required_cmdline: str | list = Field(default_factory=list)
    banned_cmdline: str | list = Field(default_factory=list)

    @field_validator("required_cmdline", mode="before")
    @classmethod
    def validate_required_cmdline(cls, required_cmdline: str | list) -> list:
        """support str or list input for required_cmdline

        Args:
            required_cmdline (str | list): _description_

        Returns:
            list: _description_
        """
        if isinstance(required_cmdline, str):
            required_cmdline = [required_cmdline]

        return required_cmdline

    @field_validator("banned_cmdline", mode="before")
    @classmethod
    def validate_banned_cmdline(cls, banned_cmdline: str | list) -> list:
        """support str or list input for banned_cmdline

        Args:
            banned_cmdline (str | list): _description_

        Returns:
            list: _description_
        """
        if isinstance(banned_cmdline, str):
            banned_cmdline = [banned_cmdline]

        return banned_cmdline
