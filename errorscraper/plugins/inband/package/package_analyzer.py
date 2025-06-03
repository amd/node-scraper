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
import re
from typing import Optional

from errorscraper.enums import EventCategory, EventPriority, ExecutionStatus
from errorscraper.interfaces import DataAnalyzer
from errorscraper.models import TaskResult

from .analyzer_args import PackageAnalyzerArgs
from .packagedata import PackageDataModel


class PackageAnalyzer(DataAnalyzer[PackageDataModel, PackageAnalyzerArgs]):
    """Check the package version data against the expected package version data"""

    DATA_MODEL = PackageDataModel

    def regex_version_data(
        self,
        package_data: dict[str, str],
        key_search: re.Pattern[str],
        value_search: re.Pattern[str] | None,
    ) -> bool:
        """Searches the package values for the key and value search patterns

        Args:
            package_data (dict[str, str]): a dictionary of package names and versions
            key_search (re.Pattern[str]): a compiled regex pattern to search for the package name
            value_search (re.Pattern[str] | None): a compiled regex pattern to search for the package version, if None then any version is accepted

        Returns:
            bool: A boolean indicating if the value was found
        """

        value_found = False
        for name, version in package_data.items():
            key_search_res = key_search.search(name)
            if key_search_res:
                value_found = True
                if value_search is None:
                    continue
                value_search_res = value_search.search(version)
                if not value_search_res:
                    self._log_event(
                        EventCategory.APPLICATION,
                        f"Package {key_search.pattern} Version Mismatch, Expected {value_search.pattern} but found {version}",
                        EventPriority.ERROR,
                        {
                            "expected_package_search": key_search.pattern,
                            "found_package": name,
                            "expected_version_search": value_search.pattern,
                            "found_version": version,
                        },
                    )
        return value_found

    def package_regex_search(
        self, package_data: dict[str, str], exp_packge_data: dict[str, str | None]
    ):
        """Searches the package data for the expected package and version using regex

        Args:
            package_data (dict[str, str]): a dictionary of package names and versions
            exp_packge_data (dict[str, str  |  None]): a dictionary of expected package names and versions
        """
        for exp_key, exp_value in exp_packge_data.items():
            try:
                if exp_value is not None:
                    value_search = re.compile(exp_value)
                else:
                    value_search = None
                key_search = re.compile(exp_key)
            except re.error:
                self._log_event(
                    EventCategory.RUNTIME,
                    f"Regex Compile Error either {exp_key} {exp_value}",
                    EventPriority.ERROR,
                    {
                        "expected_package_search": exp_key,
                        "expected_version_search": exp_value,
                    },
                )
                continue

            key_found = self.regex_version_data(package_data, key_search, value_search)

            if not key_found:
                self._log_event(
                    EventCategory.APPLICATION,
                    f"Package {exp_key} not found in the package list",
                    EventPriority.ERROR,
                    {
                        "expected_package": exp_key,
                        "found_package": None,
                        "expected_version": exp_value,
                        "found_version": None,
                    },
                )

    def package_exact_match(
        self, package_data: dict[str, str], exp_packge_data: dict[str, str | None]
    ):
        """Checks the package data for the expected package and version using exact match

        Args:
            package_data (dict[str, str]): a dictionary of package names and versions
            exp_packge_data (dict[str, str  |  None]): a dictionary of expected package names and versions
        """
        for exp_key, exp_value in exp_packge_data.items():
            self.logger.info(exp_key)
            version = package_data.get(exp_key)
            if exp_value is None:
                # allow any version when expected version is None
                if version is None:
                    # package not found
                    self._log_event(
                        EventCategory.APPLICATION,
                        f"Package {exp_key} not found in the package list",
                        EventPriority.ERROR,
                        {
                            "expected_package": exp_key,
                            "found_package": None,
                            "expected_version": exp_value,
                            "found_version": None,
                        },
                    )
            elif version != exp_value:
                self._log_event(
                    EventCategory.APPLICATION,
                    f"Package {exp_key} Version Mismatch, Expected {exp_key} but found {version}",
                    EventPriority.ERROR,
                    {
                        "expected_package": exp_key,
                        "found_package": exp_key if version else None,
                        "expected_version": exp_value,
                        "found_version": version,
                    },
                )

    def analyze_data(
        self, data: PackageDataModel, args: Optional[PackageAnalyzerArgs] = None
    ) -> TaskResult:
        """Analyze the package data against the expected package version data

        Args:
            data (PackageDataModel): package data to analyze
            args (Optional[PackageAnalyzerArgs], optional): package analysis arguments. Defaults to None.

        Returns:
            TaskResult: the result of the analysis containing status and message
        """
        if not args or not args.exp_package_ver:
            self.result.message = "Expected Package Version Data not provided"
            self.result.status = ExecutionStatus.NOT_RAN
            return self.result

        if args.regex_match:
            self.package_regex_search(data.version_info, args.exp_package_ver)
        else:
            self.package_exact_match(data.version_info, args.exp_package_ver)

        return self.result
