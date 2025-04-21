from errorscraper.base import InBandDataPlugin

from .analyzer_args import UserAnalyzerArgs
from .user_analyzer import UserAnalyzer
from .user_collector import UserCollector
from .userdata import UserDataModel


class UserPlugin(InBandDataPlugin[UserDataModel, None, UserAnalyzerArgs]):
    """Plugin for collection and analysis of user data"""

    DATA_MODEL = UserDataModel

    COLLECTOR = UserCollector

    ANALYZER = UserAnalyzer
