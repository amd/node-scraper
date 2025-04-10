from typing import Annotated, Optional, Union

from paramiko import PKey
from pydantic import BaseModel, ConfigDict, Field, SecretStr
from pydantic.networks import IPvAnyAddress


class SSHConnectionParams(BaseModel):
    """Class which holds info for an SSH connection"""

    model_config = ConfigDict(arbitrary_types_allowed=True)
    hostname: Union[IPvAnyAddress, str]
    username: str
    password: Optional[SecretStr] = None
    pkey: Optional[PKey] = None
    key_filename: Optional[str] = None
    port: Annotated[int, Field(strict=True, gt=0, lt=65536)] = 22
