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
from nodescraper.interfaces import PluginResultCollator
from nodescraper.models import PluginResult, TaskResult


class TableSummary(PluginResultCollator):
    """generate a summary of plugin results in a tabular format which will be logged using the logger instance"""

    def collate_results(
        self, plugin_results: list[PluginResult], connection_results: list[TaskResult], **kwargs
    ):
        """Collate the results into a summary table

        Args:
            plugin_results (list[PluginResult]): list of plugin results to collate
            connection_results (list[TaskResult]): list of connection results to collate
        """

        def gen_str_table(headers: list[str], rows: list[list[str | None]]):
            column_widths = [len(header) for header in headers]
            for row in rows:
                for i, cell in enumerate(row):
                    column_widths[i] = max(
                        column_widths[i],
                        len(str(cell)),
                    )
            border = f"+{'+'.join('-' * (width + 2) for width in column_widths)}+"

            def gen_row(row):
                return f"|  {' | '.join(str(cell).ljust(width) for cell, width in zip(row, column_widths, strict=False))} |"

            table = [border, gen_row(headers), border, *[gen_row(row) for row in rows], border]
            return "\n".join(table)

        tables = ""
        if connection_results:
            rows = []
            for result in connection_results:
                rows.append([result.task, result.status.name, result.message])

            table = gen_str_table(["Connection", "Status", "Message"], rows)
            tables += f"\n\n{table}"

        if plugin_results:
            rows = []
            for plugin_result in plugin_results:
                rows.append(
                    [plugin_result.source, plugin_result.status.name, plugin_result.message]
                )

            table = gen_str_table(["Plugin", "Status", "Message"], rows)
            tables += f"\n\n{table}"

        if tables:
            self.logger.info("%s\n", tables)
