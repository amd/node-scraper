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
from typing import Optional, Pattern

from nodescraper.enums import EventCategory, EventPriority, ExecutionStatus
from nodescraper.interfaces import DataAnalyzer
from nodescraper.models import TaskResult

from .analyzer_args import PackageAnalyzerArgs
from .packagedata import PackageDataModel


class PackageAnalyzer(DataAnalyzer[PackageDataModel, PackageAnalyzerArgs]):
    """Check the package version data against the expected package version data"""

    DATA_MODEL = PackageDataModel

    def regex_version_data(
        self,
        package_data: dict[str, str],
        key_search: re.Pattern[str],
        value_search: Optional[Pattern[str]],
    ) -> tuple[bool, list[tuple[str, str, str]]]:
        """Searches the package values for the key and value search patterns

        Args:
            package_data (dict[str, str]): a dictionary of package names and versions
            key_search (re.Pattern[str]): a compiled regex pattern to search for the package name
            value_search (Optional[Pattern[str]]): a compiled regex pattern to search for the package version, if None then any version is accepted

        Returns:
            tuple: (value_found, version_mismatches) where value_found is a bool and
                   version_mismatches is a list of (package_name, expected_pattern, found_version) tuples
        """

        value_found = False
        version_mismatches = []
        for name, version in package_data.items():
            self.logger.debug("Package data: %s, %s", name, version)
            key_search_res = key_search.search(name)
            if key_search_res:
                value_found = True
                if value_search is None:
                    continue
                value_search_res = value_search.search(version)
                if not value_search_res:
                    version_mismatches.append((name, value_search.pattern, version))
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
        return value_found, version_mismatches

    def package_regex_search(
        self, package_data: dict[str, str], exp_package_data: dict[str, Optional[str]]
    ):
        """Searches the package data for the expected package and version using regex

        Args:
            package_data (dict[str, str]): a dictionary of package names and versions
            exp_package_data (dict[str, Optional[str]]): a dictionary of expected package names and versions

        Returns:
            tuple: (not_found_keys, regex_errors, version_mismatches) containing lists of errors
        """
        not_found_keys = []
        regex_errors = []
        version_mismatches = []

        for exp_key, exp_value in exp_package_data.items():
            try:
                if exp_value is not None:
                    value_search = re.compile(exp_value)
                else:
                    value_search = None
                key_search = re.compile(exp_key)
            except re.error as e:
                regex_errors.append((exp_key, exp_value, str(e)))
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

            key_found, mismatches = self.regex_version_data(package_data, key_search, value_search)

            # Collect version mismatches
            version_mismatches.extend(mismatches)

            if not key_found:
                not_found_keys.append((exp_key, exp_value))
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

        return not_found_keys, regex_errors, version_mismatches

    def package_exact_match(
        self, package_data: dict[str, str], exp_package_data: dict[str, Optional[str]]
    ):
        """Checks the package data for the expected package and version using exact match

        Args:
            package_data (dict[str, str]): a dictionary of package names and versions
            exp_package_data (dict[str, Optional[str]]): a dictionary of expected package names and versions
        """
        not_found_match = []
        not_found_version = []
        for exp_key, exp_value in exp_package_data.items():
            self.logger.info("Expected value: %s, %s", exp_key, exp_value)
            version = package_data.get(exp_key)
            self.logger.info("Found version: %s", version)
            if version is None:
                # package not found
                not_found_version.append((exp_key, exp_value))
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
            elif exp_value is None:
                # allow any version when expected version is None
                continue
            elif version != exp_value:
                not_found_match.append((exp_key, version))
                self._log_event(
                    EventCategory.APPLICATION,
                    f"Package {exp_key} Version Mismatch, Expected {exp_value} but found {version}",
                    EventPriority.ERROR,
                    {
                        "expected_package": exp_key,
                        "found_package": exp_key,
                        "expected_version": exp_value,
                        "found_version": version,
                    },
                )
        return not_found_match, not_found_version

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
            not_found_keys, regex_errors, version_mismatches = self.package_regex_search(
                data.version_info, args.exp_package_ver
            )

            # Adding details for err message
            error_parts = []
            if not_found_keys:
                packages_detail = ", ".join(
                    [
                        f"'{pkg}' (expected version: {ver if ver else 'any'})"
                        for pkg, ver in not_found_keys
                    ]
                )
                error_parts.append(f"Packages not found: {packages_detail}")

            if regex_errors:
                regex_detail = ", ".join(
                    [f"'{pkg}' pattern (version: {ver})" for pkg, ver, _ in regex_errors]
                )
                error_parts.append(f"Regex compile errors: {regex_detail}")

            if version_mismatches:
                version_detail = ", ".join(
                    [
                        f"'{pkg}' (expected: {exp}, found: {found})"
                        for pkg, exp, found in version_mismatches
                    ]
                )
                error_parts.append(f"Version mismatches: {version_detail}")

            total_errors = len(not_found_keys) + len(regex_errors) + len(version_mismatches)
            if total_errors > 0:
                self.result.message = "Package version mismatch"
                self.result.status = ExecutionStatus.ERROR
            else:
                self.result.message = "All packages found and versions matched"
                self.result.status = ExecutionStatus.OK
        else:
            self.logger.info("Expected packages: %s", list(args.exp_package_ver.keys()))
            not_found_match, not_found_version = self.package_exact_match(
                data.version_info, args.exp_package_ver
            )
            if not_found_match or not_found_version:
                self.result.message = "Package version mismatch"
                self.result.status = ExecutionStatus.ERROR

        return self.result
