###############################################################################
#
# MIT License
#
# Copyright (c) 2026 Advanced Micro Devices, Inc.
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
from typing import Optional

from nodescraper.base import RedfishDataCollector
from nodescraper.enums import EventCategory, EventPriority, ExecutionStatus
from nodescraper.models import TaskResult

from .collector_args import RedfishEndpointCollectorArgs
from .endpoint_data import RedfishEndpointDataModel


def _uris_from_args(args: Optional[RedfishEndpointCollectorArgs]) -> list[str]:
    """Return list of URIs from collector args.uris."""
    if args is None:
        return []
    return list(args.uris) if args.uris else []


class RedfishEndpointCollector(
    RedfishDataCollector[RedfishEndpointDataModel, RedfishEndpointCollectorArgs]
):
    """Collects Redfish endpoint responses for URIs specified in config."""

    DATA_MODEL = RedfishEndpointDataModel

    def collect_data(
        self, args: Optional[RedfishEndpointCollectorArgs] = None
    ) -> tuple[TaskResult, Optional[RedfishEndpointDataModel]]:
        """GET each configured Redfish URI via _run_redfish_get() and store the JSON response."""
        uris = _uris_from_args(args)
        if not uris:
            self.result.message = "No Redfish URIs configured"
            self.result.status = ExecutionStatus.NOT_RAN
            return self.result, None

        responses: dict[str, dict] = {}
        for uri in uris:
            path = uri
            if not path:
                continue
            if not path.startswith("/"):
                path = "/" + path
            res = self._run_redfish_get(path, log_artifact=True)
            if res.success and res.data is not None:
                responses[res.path] = res.data
            else:
                self._log_event(
                    category=EventCategory.RUNTIME,
                    description=f"Redfish GET failed for {path}: {res.error or 'unknown'}",
                    priority=EventPriority.WARNING,
                    console_log=True,
                )

        if not responses:
            self.result.message = "No Redfish endpoints could be read"
            self.result.status = ExecutionStatus.ERROR
            return self.result, None

        data = RedfishEndpointDataModel(responses=responses)
        self.result.message = f"Collected {len(responses)} Redfish endpoint(s)"
        self.result.status = ExecutionStatus.OK
        return self.result, data
