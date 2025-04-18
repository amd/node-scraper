from pydantic import BaseModel, Field

from errorscraper.models import DataModel


class LastData(BaseModel):
    """
    last reads contents of /var/log/wtmp file
    wtmp records username, terminal, ip address, login time, logout time, duration
    null username indicates logout
    terminal name (with username shutdown or reboot) indicates system shutdown or reboot
    """

    user: str
    terminal: str
    ip_address: str
    login_time: str
    logout_time: str | None
    duration: str | None


class LastDataModel(DataModel):
    last_data: list[LastData] = Field(default_factory=list)
