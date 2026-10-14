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
from typing import Any

from nodescraper.enums import OSFamily
from nodescraper.plugins.registers.collector_args import RegisterDecodeCollectorArgs
from nodescraper.plugins.registers.register_decode_collector import (
    RegisterDecodeCollector,
)

from .collector_args import McaRegisterDecodeCollectorArgs
from .mca_register_decode_data import McaRegisterDecodeDataModel


class McaRegisterDecodeCollector(RegisterDecodeCollector):
    """Read MCA registers through an installed register-tool entry point."""

    DATA_MODEL = McaRegisterDecodeDataModel
    SUPPORTED_OS_FAMILY: set[OSFamily] = {OSFamily.LINUX}
    SUPPORTED_SKUS = {"MI450", "MI455", "MI4XX"}

    def _default_args(self) -> McaRegisterDecodeCollectorArgs:
        """Build MCA collector args when the caller omitted them.

        Returns:
            Default MCA collector args.
        """
        return McaRegisterDecodeCollectorArgs()

    def _record_name(self) -> str:
        """Return the record name used in result messages.

        Returns:
            Record name.
        """
        return "MCA register"

    def _remote_message(self) -> str:
        """Return the message used when collection is remote.

        Returns:
            Remote-system message.
        """
        return "MCA register collection is only supported on local"

    def _read_registers(self, tool: Any, args: RegisterDecodeCollectorArgs) -> Any:
        """Read MCA registers for the selected CPUs and banks.

        Args:
            tool: Discovered register tool.
            args: Collector arguments.

        Returns:
            Tool collection result.
        """
        return tool.collect(
            threads=getattr(args, "threads", None),
            banks=getattr(args, "banks", None),
            verbose=getattr(args, "verbose", False),
            capture_all=getattr(args, "capture_all", False),
        )
