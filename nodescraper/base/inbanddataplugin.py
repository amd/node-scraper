###############################################################################
#
# MIT License
#
# Copyright (c) 2025 Advanced Micro Devices, Inc.
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
#
###############################################################################
import json
import os
from pathlib import Path
from typing import Any, Generic, Optional

from nodescraper.connection.inband import InBandConnectionManager, SSHConnectionParams
from nodescraper.generictypes import TAnalyzeArg, TCollectArg, TDataModel
from nodescraper.interfaces import DataPlugin
from nodescraper.models import DataModel
from nodescraper.utils import pascal_to_snake


class InBandDataPlugin(
    DataPlugin[InBandConnectionManager, SSHConnectionParams, TDataModel, TCollectArg, TAnalyzeArg],
    Generic[TDataModel, TCollectArg, TAnalyzeArg],
):
    """Base class for in band plugins.

    Supports loading and comparing plugin data from scraper run directories
    (e.g. for compare-runs). Subclasses get find_datamodel_path_in_run,
    load_datamodel_from_path, get_extracted_errors, and load_run_data.
    """

    CONNECTION_TYPE = InBandConnectionManager

    @classmethod
    def find_datamodel_path_in_run(cls, run_path: str) -> Optional[str]:
        """Find this plugin's collector datamodel file under a scraper run directory.

        Looks for <run_path>/<plugin_snake>/<collector_snake>/ with result.json
        whose parent matches this plugin, then a datamodel file (datamodel.json,
        <data_model_name>.json, or .log).

        Args:
            run_path: Path to a scraper log run directory (e.g. scraper_logs_*).

        Returns:
            Absolute path to the datamodel file, or None if not found.
        """
        run_path = os.path.abspath(run_path)
        if not os.path.isdir(run_path):
            return None
        collector_cls = getattr(cls, "COLLECTOR", None)
        data_model_cls = getattr(cls, "DATA_MODEL", None)
        if not collector_cls or not data_model_cls:
            return None
        collector_dir = os.path.join(
            run_path,
            pascal_to_snake(cls.__name__),
            pascal_to_snake(collector_cls.__name__),
        )
        if not os.path.isdir(collector_dir):
            return None
        result_path = os.path.join(collector_dir, "result.json")
        if not os.path.isfile(result_path):
            return None
        try:
            res_payload = json.loads(Path(result_path).read_text(encoding="utf-8"))
            if res_payload.get("parent") != cls.__name__:
                return None
        except (json.JSONDecodeError, OSError):
            return None
        want_json = data_model_cls.__name__.lower() + ".json"
        for fname in os.listdir(collector_dir):
            low = fname.lower()
            if low.endswith("datamodel.json") or low == want_json:
                return os.path.join(collector_dir, fname)
            if low.endswith(".log"):
                return os.path.join(collector_dir, fname)
        return None

    @classmethod
    def load_datamodel_from_path(cls, dm_path: str) -> Optional[TDataModel]:
        """Load this plugin's DATA_MODEL from a file path (JSON or .log).

        Args:
            dm_path: Path to datamodel JSON or to a .log file (if DATA_MODEL
                implements import_model for that format).

        Returns:
            Instance of DATA_MODEL or None if load fails.
        """
        dm_path = os.path.abspath(dm_path)
        if not os.path.isfile(dm_path):
            return None
        data_model_cls = getattr(cls, "DATA_MODEL", None)
        if not data_model_cls:
            return None
        try:
            if dm_path.lower().endswith(".log"):
                import_model = getattr(data_model_cls, "import_model", None)
                if not callable(import_model):
                    return None
                base_import = getattr(DataModel.import_model, "__func__", DataModel.import_model)
                if getattr(import_model, "__func__", import_model) is base_import:
                    return None
                return import_model(dm_path)
            with open(dm_path, encoding="utf-8") as f:
                data = json.load(f)
            return data_model_cls.model_validate(data)
        except (json.JSONDecodeError, OSError, Exception):
            return None

    @classmethod
    def get_extracted_errors(cls, data_model: DataModel) -> Optional[list[str]]:
        """Compute extracted errors from datamodel for compare-runs (in memory only).

        Uses get_compare_content() on the datamodel and ANALYZER.get_error_matches
        if this plugin has an ANALYZER; otherwise returns None.

        Args:
            data_model: Loaded DATA_MODEL instance.

        Returns:
            Sorted list of error match strings, or None if not applicable.
        """
        get_content = getattr(data_model, "get_compare_content", None)
        if not callable(get_content):
            return None
        try:
            content = get_content()
        except Exception:
            return None
        if not isinstance(content, str):
            return None
        analyzer_cls = getattr(cls, "ANALYZER", None)
        if not analyzer_cls:
            return None
        get_matches = getattr(analyzer_cls, "get_error_matches", None)
        if not callable(get_matches):
            return None
        try:
            matches = get_matches(content)
            return sorted(matches) if matches is not None else None
        except Exception:
            return None

    @classmethod
    def load_run_data(cls, run_path: str) -> Optional[dict[str, Any]]:
        """Load this plugin's run data from a scraper run directory for comparison.

        Finds the datamodel file, loads it, and returns a JSON-serializable dict
        (model_dump) with optional "extracted_errors" if the plugin supports
        get_compare_content and ANALYZER.get_error_matches.

        Args:
            run_path: Path to a scraper log run directory or to a datamodel file.

        Returns:
            Dict suitable for diffing with another run, or None if not found.
        """
        run_path = os.path.abspath(run_path)
        if not os.path.exists(run_path):
            return None
        dm_path = run_path if os.path.isfile(run_path) else cls.find_datamodel_path_in_run(run_path)
        if not dm_path:
            return None
        data_model = cls.load_datamodel_from_path(dm_path)
        if data_model is None:
            return None
        out = data_model.model_dump(mode="json")
        extracted = cls.get_extracted_errors(data_model)
        if extracted is not None:
            out["extracted_errors"] = extracted
        return out
