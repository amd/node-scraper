from pydantic import BaseModel, Field, field_validator


class UserAnalyzerArgs(BaseModel):
    allowed_users: str | list = Field(default_factory=list)

    @field_validator("allowed_users", mode="before")
    @classmethod
    def validate_allowed_users(cls, allowed_users: str | list) -> list:
        """support str or list input for allowed_users

        Args:
            allowed_users (str | list): allowed_users input

        Returns:
            list: allowed_users list
        """
        if isinstance(allowed_users, str):
            allowed_users = [allowed_users]

        return allowed_users
