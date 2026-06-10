"""Generic command collection plugins (in-band and OOB SSH)."""

from .analyzer_args import CommandCheck, GenericAnalyzerArgs
from .collector_args import CommandSpec, GenericCollectionCollectorArgs
from .generic_analyzer import GenericAnalyzer
from .generic_collection_collector import GenericCollectionCollector
from .generic_collection_data import CommandCollectionResult, GenericCollectionDataModel
from .generic_collection_plugin_mixin import GenericCollectionPluginMixin
from .inband_plugin import GenericCollectionPlugin
from .oob_plugin import OOBGenericCollectionPlugin

__all__ = [
    "CommandCheck",
    "CommandCollectionResult",
    "CommandSpec",
    "GenericAnalyzer",
    "GenericAnalyzerArgs",
    "GenericCollectionCollector",
    "GenericCollectionCollectorArgs",
    "GenericCollectionDataModel",
    "GenericCollectionPlugin",
    "GenericCollectionPluginMixin",
    "OOBGenericCollectionPlugin",
]
