from errorscraper.base import InBandDataPlugin

from .analyzer_args import PackageAnalyzerArgs
from .package_analyzer import PackageAnalyzer
from .package_collector import PackageCollector
from .packagedata import PackageDataModel


class PackagePlugin(InBandDataPlugin[PackageDataModel, None, PackageAnalyzerArgs]):
    """Plugin for collection and analysis of package version data"""

    DATA_MODEL = PackageDataModel

    COLLECTOR = PackageCollector

    ANALYZER = PackageAnalyzer
