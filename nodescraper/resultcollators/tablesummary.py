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
from textwrap import wrap

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

        def gen_str_table(
            headers: list[str],
            rows: list[list[str | None]],
            max_widths: dict[str, int] | None = None,
        ) -> str:
            """
            Wrap cells.
            """
            max_widths = max_widths or {}

            norm_rows: list[list[str]] = [
                ["" if c is None else str(c) for c in row] for row in rows
            ]

            ncols = len(headers)

            raw_widths: list[int] = [len(h) for h in headers]
            for norm_row in norm_rows:
                for i, cell in enumerate(norm_row):
                    for part in cell.splitlines() or [""]:
                        if len(part) > raw_widths[i]:
                            raw_widths[i] = len(part)

            target_widths: list[int] = []
            for i, h in enumerate(headers):
                cap = max_widths.get(h)
                if cap is None:
                    target_widths.append(raw_widths[i])
                else:
                    target_widths.append(max(len(h), min(raw_widths[i], cap)))

            wrapped_rows: list[list[list[str]]] = []
            for norm_row in norm_rows:
                wrapped_cells: list[list[str]] = []
                for i, cell in enumerate(norm_row):
                    cell_lines: list[str] = []
                    paragraphs = cell.splitlines() or [""]
                    for para in paragraphs:
                        chunked = wrap(para, width=target_widths[i]) or [""]
                        cell_lines.extend(chunked)
                    wrapped_cells.append(cell_lines)
                wrapped_rows.append(wrapped_cells)

            col_widths: list[int] = []
            for i in range(ncols):
                widest_line = len(headers[i])
                for wrow in wrapped_rows:
                    for line in wrow[i]:
                        if len(line) > widest_line:
                            widest_line = len(line)
                col_widths.append(widest_line)

            border = "+" + "+".join("-" * (w + 2) for w in col_widths) + "+"

            def render_physical_row(parts: list[str]) -> str:
                return (
                    "| "
                    + " | ".join(p.ljust(w) for p, w in zip(parts, col_widths, strict=False))
                    + " |"
                )

            table_lines: list[str] = [border, render_physical_row(headers), border]
            for wrow in wrapped_rows:
                height = max(len(cell_lines) for cell_lines in wrow)
                for idx in range(height):
                    parts = [
                        (wrow[col][idx] if idx < len(wrow[col]) else "") for col in range(ncols)
                    ]
                    table_lines.append(render_physical_row(parts))
            table_lines.append(border)
            return "\n".join(table_lines)

        tables = ""
        if connection_results:
            # Allow Optional[str] elements
            conn_rows: list[list[str | None]] = []
            for connection_result in connection_results:
                conn_rows.append(
                    [
                        connection_result.task,
                        connection_result.status.name,
                        connection_result.message,
                    ]
                )

            table = gen_str_table(
                ["Connection", "Status", "Message"],
                conn_rows,
                max_widths={"Connection": 32, "Status": 16, "Message": 80},
            )
            tables += f"\n\n{table}"

        if plugin_results:
            # Allow Optional[str] elements
            plug_rows: list[list[str | None]] = []
            for plugin_result in plugin_results:
                plug_rows.append(
                    [
                        plugin_result.source,
                        plugin_result.status.name,
                        plugin_result.message,
                    ]
                )
            table = gen_str_table(
                ["Plugin", "Status", "Message"],
                plug_rows,
                max_widths={"Plugin": 32, "Status": 16, "Message": 80},
            )
            tables += f"\n\n{table}"

        if tables:
            self.logger.info("%s\n", tables)
