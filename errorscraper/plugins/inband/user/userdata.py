from errorscraper.models import DataModel


class UserDataModel(DataModel):
    active_users: list[str]
