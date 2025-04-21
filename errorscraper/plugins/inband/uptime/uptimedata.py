from errorscraper.models import DataModel


class UptimeDataModel(DataModel):
    current_time: str
    uptime: str
