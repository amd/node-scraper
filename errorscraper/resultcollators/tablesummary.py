from errorscraper.interfaces import PluginResultCollator
from errorscraper.models import PluginResult, TaskResult


def gen_str_table(headers: list[str], rows: list[str]):
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


class TableSummary(PluginResultCollator):

    def collate_results(
        self, plugin_results: list[PluginResult], connection_results: list[TaskResult], **kwargs
    ):
        tables = ""
        if connection_results:
            rows = []
            for result in connection_results:
                rows.append([result.task, result.status.name, result.message])

            table = gen_str_table(["Connection", "Status", "Message"], rows)
            tables += f"\n\n{table}"

        if plugin_results:
            rows = []
            for result in plugin_results:
                rows.append([result.source, result.status.name, result.message])

            table = gen_str_table(["Plugin", "Status", "Message"], rows)
            tables += f"\n\n{table}"

        if tables:
            self.logger.info(tables + "\n")
