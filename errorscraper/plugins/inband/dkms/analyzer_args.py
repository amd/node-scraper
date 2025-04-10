from pydantic import BaseModel, Field, field_validator


class DkmsAnalyzerArgs(BaseModel):
    dkms_status: str | list = Field(default_factory=list)
    dkms_version: str | list = Field(default_factory=list)
    regex_match: bool = False

    @field_validator("dkms_status", mode="before")
    @classmethod
    def validate_dkms_status(cls, dkms_status: str | list) -> list:
        """support str or list input for dkms_status

        Args:
            dkms_status (str | list): _description_

        Returns:
            list: _description_
        """
        if isinstance(dkms_status, str):
            dkms_status = [dkms_status]

        return dkms_status

    @field_validator("dkms_version", mode="before")
    @classmethod
    def validate_dkms_version(cls, dkms_version: str | list) -> list:
        """support str or list input for dkms_version

        Args:
            dkms_version (str | list): _description_

        Returns:
            list: _description_
        """
        if isinstance(dkms_version, str):
            dkms_version = [dkms_version]

        return dkms_version
