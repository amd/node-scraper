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
import html
import json
import os
from typing import Optional

from nodescraper.interfaces import PluginResultCollator
from nodescraper.models import PluginResult, TaskResult

ARTIFACT_PREFIX = "command_artifacts"
ARTIFACT_SUFFIX = ".json"
HTML_SUFFIX = ".html"

_HTML_HEAD = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Command Artifacts</title>
<style>
  :root {
    --bg: #0d1117;
    --panel: #161b22;
    --panel-hover: #1c2330;
    --border: #30363d;
    --text: #e6edf3;
    --muted: #8b949e;
    --accent: #58a6ff;
    --ok-bg: #1a3326; --ok-fg: #4ac26b;
    --fail-bg: #3a1d1d; --fail-fg: #f85149;
  }
  * { box-sizing: border-box; }
  body {
    margin: 0;
    background: var(--bg);
    color: var(--text);
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
    line-height: 1.5;
  }
  header {
    position: sticky; top: 0; z-index: 10;
    background: var(--panel);
    border-bottom: 1px solid var(--border);
    padding: 16px 24px;
  }
  header h1 { margin: 0 0 4px; font-size: 18px; }
  header .sub { color: var(--muted); font-size: 13px; word-break: break-all; }
  .controls {
    display: flex; gap: 8px; align-items: center; margin-top: 12px; flex-wrap: wrap;
  }
  .controls input {
    flex: 1 1 280px; min-width: 200px;
    background: var(--bg); color: var(--text);
    border: 1px solid var(--border); border-radius: 6px;
    padding: 8px 12px; font-size: 14px;
  }
  .controls button {
    background: var(--bg); color: var(--text);
    border: 1px solid var(--border); border-radius: 6px;
    padding: 8px 12px; font-size: 13px; cursor: pointer;
  }
  .controls button:hover { background: var(--panel-hover); border-color: var(--accent); }
  main { padding: 16px 24px 64px; max-width: 1400px; margin: 0 auto; }
  details.cmd {
    background: var(--panel);
    border: 1px solid var(--border);
    border-radius: 8px;
    margin-bottom: 10px;
    overflow: hidden;
  }
  details.cmd summary {
    display: flex; align-items: center; gap: 10px;
    padding: 12px 14px; cursor: pointer; list-style: none;
    user-select: none;
  }
  details.cmd summary::-webkit-details-marker { display: none; }
  details.cmd summary:hover { background: var(--panel-hover); }
  .chevron { color: var(--muted); transition: transform .15s ease; font-size: 12px; }
  details.cmd[open] .chevron { transform: rotate(90deg); }
  code.title {
    flex: 1;
    font-family: "SFMono-Regular", Consolas, "Liberation Mono", Menlo, monospace;
    font-size: 13.5px; color: var(--accent); word-break: break-all;
  }
  .badge {
    flex: 0 0 auto;
    font-size: 11px; font-weight: 600;
    padding: 3px 8px; border-radius: 12px;
    font-family: "SFMono-Regular", Consolas, monospace;
  }
  .badge.ok { background: var(--ok-bg); color: var(--ok-fg); }
  .badge.fail { background: var(--fail-bg); color: var(--fail-fg); }
  .body { border-top: 1px solid var(--border); }
  pre {
    margin: 0; padding: 14px 16px;
    overflow-x: auto;
    font-family: "SFMono-Regular", Consolas, "Liberation Mono", Menlo, monospace;
    font-size: 12.5px; line-height: 1.45;
    white-space: pre; color: var(--text);
  }
  pre.empty { color: var(--muted); font-style: italic; }
  .stderr-label {
    padding: 6px 16px 0; color: var(--fail-fg);
    font-size: 12px; font-weight: 600; text-transform: uppercase; letter-spacing: .5px;
  }
  pre.stderr { color: var(--fail-fg); }
  .no-results { color: var(--muted); padding: 24px; text-align: center; display: none; }
</style>
</head>
<body>
"""

_HEADER_TEMPLATE = """<header>
  <h1>Command Artifacts</h1>
  <div class="sub">{count} commands &middot; {title}</div>
  <div class="controls">
    <input id="filter" type="text" placeholder="Filter commands&hellip;" autocomplete="off">
    <button id="expandAll" type="button">Expand all</button>
    <button id="collapseAll" type="button">Collapse all</button>
  </div>
</header>
<main id="list">
"""

_CARD_TEMPLATE = """    <details class="cmd">
      <summary>
        <span class="chevron">&#9656;</span>
        <code class="title">{command}</code>
        <span class="badge {badge_cls}">exit {exit_code}</span>
      </summary>
      <div class="body">
        {stdout_block}
        {stderr_block}
      </div>
    </details>"""

_HTML_TAIL = """
  <div class="no-results" id="noResults">No commands match your filter.</div>
</main>
<script>
  const filter = document.getElementById('filter');
  const items = Array.from(document.querySelectorAll('details.cmd'));
  const noResults = document.getElementById('noResults');

  filter.addEventListener('input', () => {
    const q = filter.value.trim().toLowerCase();
    let visible = 0;
    items.forEach(d => {
      const title = d.querySelector('.title').textContent.toLowerCase();
      const match = title.includes(q);
      d.style.display = match ? '' : 'none';
      if (match) visible++;
    });
    noResults.style.display = visible ? 'none' : 'block';
  });

  document.getElementById('expandAll').addEventListener('click', () => {
    items.forEach(d => { if (d.style.display !== 'none') d.open = true; });
  });
  document.getElementById('collapseAll').addEventListener('click', () => {
    items.forEach(d => d.open = false);
  });
</script>
</body>
</html>
"""


def render_command_artifacts_html(entries: list[dict], title: str) -> str:
    """Render a list of command artifact entries into a self-contained HTML page.

    Each entry is shown as a collapsible dropdown titled with the command, with the
    stdout (and stderr, when present) revealed inside.

    Args:
        entries (list[dict]): command artifact records with ``command``/``stdout``/
            ``stderr``/``exit_code`` keys.
        title (str): label shown in the page header (e.g. the collector path).

    Returns:
        str: full HTML document.
    """
    cards: list[str] = []
    for entry in entries:
        command = html.escape(str(entry.get("command", "") or ""))
        stdout = str(entry.get("stdout", "") or "")
        stderr = str(entry.get("stderr", "") or "")
        exit_code = entry.get("exit_code", "")
        badge_cls = "ok" if exit_code == 0 else "fail"

        if stdout.strip():
            stdout_block = "<pre>" + html.escape(stdout) + "</pre>"
        else:
            stdout_block = '<pre class="empty">(no stdout)</pre>'

        if stderr.strip():
            stderr_block = (
                '<div class="stderr-label">stderr</div>'
                '<pre class="stderr">' + html.escape(stderr) + "</pre>"
            )
        else:
            stderr_block = ""

        cards.append(
            _CARD_TEMPLATE.format(
                command=command,
                badge_cls=badge_cls,
                exit_code=html.escape(str(exit_code)),
                stdout_block=stdout_block,
                stderr_block=stderr_block,
            )
        )

    return (
        _HTML_HEAD
        + _HEADER_TEMPLATE.format(count=len(entries), title=html.escape(title))
        + "\n".join(cards)
        + _HTML_TAIL
    )


class CommandArtifactHtml(PluginResultCollator):
    """Generate browsable HTML artifacts from ``command_artifacts.json`` files.

    Disabled by default. Enable it by adding ``CommandArtifactHtml`` to the
    ``result_collators`` section of a plugin config, or by passing ``--html-artifact``
    on the CLI. For every ``command_artifacts.json`` found under the run log
    directory, a sibling ``command_artifacts.html`` is written where each command is
    a collapsible dropdown revealing its stdout (and stderr when present).
    """

    def collate_results(
        self, plugin_results: list[PluginResult], connection_results: list[TaskResult], **kwargs
    ):
        """Walk the run log directory and render an HTML artifact per artifact file.

        Args:
            plugin_results (list[PluginResult]): plugin results (unused; artifacts are
                read from the files already written to ``log_path``).
            connection_results (list[TaskResult]): connection results (unused).
        """
        if not self.log_path:
            self.logger.warning(
                "CommandArtifactHtml skipped: no log_path is set, nothing to generate"
            )
            return

        artifact_files = self._find_artifact_files(self.log_path)
        if not artifact_files:
            self.logger.info(
                "CommandArtifactHtml: no %s%s files found under %s",
                ARTIFACT_PREFIX,
                ARTIFACT_SUFFIX,
                self.log_path,
            )
            return

        generated = 0
        for artifact_path in artifact_files:
            html_path = self._generate_html(artifact_path)
            if html_path:
                generated += 1
                self.logger.info("Generated command artifact HTML")

    @staticmethod
    def _find_artifact_files(root: str) -> list[str]:
        """Recursively find ``command_artifacts*.json`` files under ``root``.

        Args:
            root (str): directory to search.

        Returns:
            list[str]: sorted absolute paths to matching artifact files.
        """
        matches: list[str] = []
        for dirpath, _dirnames, filenames in os.walk(root):
            for filename in filenames:
                if filename.startswith(ARTIFACT_PREFIX) and filename.endswith(ARTIFACT_SUFFIX):
                    matches.append(os.path.join(dirpath, filename))
        return sorted(matches)

    def _generate_html(self, artifact_path: str) -> Optional[str]:
        """Render a single artifact file to a sibling HTML artifact.

        Args:
            artifact_path (str): path to a ``command_artifacts*.json`` file.

        Returns:
            Optional[str]: path to the written HTML file, or None if skipped/failed.
        """
        try:
            with open(artifact_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError) as e:
            self.logger.warning("Could not read artifact file %s: %s", artifact_path, e)
            return None

        if not isinstance(data, list):
            self.logger.warning("Skipping %s: expected a list of command artifacts", artifact_path)
            return None

        artifact_dir = os.path.dirname(artifact_path)
        title = os.path.relpath(artifact_dir, self.log_path)
        if title in (".", ""):
            title = os.path.basename(os.path.normpath(artifact_dir))

        html_name = os.path.basename(artifact_path)[: -len(ARTIFACT_SUFFIX)] + HTML_SUFFIX
        html_path = os.path.join(artifact_dir, html_name)

        try:
            html_doc = render_command_artifacts_html(data, title)
            with open(html_path, "w", encoding="utf-8") as f:
                f.write(html_doc)
        except OSError as e:
            self.logger.warning("Could not write HTML artifact %s: %s", html_path, e)
            return None

        return html_path
