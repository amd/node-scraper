from errorscraper.base import InBandDataPlugin

from .uptime_collector import UptimeCollector
from .uptimedata import UptimeDataModel


class UptimePlugin(InBandDataPlugin[UptimeDataModel, None, None]):
    """Plugin for collection of system uptime data"""

    DATA_MODEL = UptimeDataModel

    COLLECTOR = UptimeCollector
