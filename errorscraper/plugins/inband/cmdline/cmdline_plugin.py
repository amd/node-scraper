from errorscraper.interfaces.inbanddataplugin import InBandDataPlugin

from .analyzer_args import CmdlineAnalyzerArgs
from .cmdline_analyzer import CmdlineAnalyzer
from .cmdline_collector import CmdlineCollector
from .cmdlinedata import CmdlineDataModel


class CmdlinePlugin(InBandDataPlugin[CmdlineDataModel, None, CmdlineAnalyzerArgs]):
    """Plugin for collection and analysis of BIOS data"""

    DATA_MODEL = CmdlineDataModel

    COLLECTOR = CmdlineCollector

    ANALYZER = CmdlineAnalyzer
