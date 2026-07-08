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

COMMAND_ARTIFACTS_BASENAME = "command_artifacts"

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
  .copy-btn {
    flex: 0 0 auto;
    display: inline-flex; align-items: center; justify-content: center;
    background: var(--bg); color: var(--muted);
    border: 1px solid var(--border); border-radius: 6px;
    padding: 5px 7px; cursor: pointer; line-height: 0;
    transition: color .15s ease, border-color .15s ease, background .15s ease;
  }
  .copy-btn:hover { background: var(--panel-hover); border-color: var(--accent); color: var(--text); }
  .copy-btn.copied { color: var(--ok-fg); border-color: var(--ok-fg); }
  .copy-btn svg { display: block; }
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
        <button class="copy-btn" type="button" title="Copy output" aria-label="Copy output">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path></svg>
        </button>
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

  const copyButtons = Array.from(document.querySelectorAll('.copy-btn'));
  const COPY_SVG = copyButtons.length ? copyButtons[0].innerHTML : '';
  const CHECK_SVG = '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"></polyline></svg>';

  function showCopied(btn) {
    btn.classList.add('copied');
    btn.innerHTML = CHECK_SVG;
    if (btn._resetTimer) clearTimeout(btn._resetTimer);
    btn._resetTimer = setTimeout(() => {
      btn.classList.remove('copied');
      btn.innerHTML = COPY_SVG;
    }, 1200);
  }

  function fallbackCopy(text, btn) {
    const ta = document.createElement('textarea');
    ta.value = text;
    ta.style.position = 'fixed';
    ta.style.top = '-1000px';
    ta.style.opacity = '0';
    document.body.appendChild(ta);
    ta.focus();
    ta.select();
    try { document.execCommand('copy'); showCopied(btn); } catch (e) {}
    document.body.removeChild(ta);
  }

  copyButtons.forEach(btn => {
    btn.addEventListener('click', (e) => {
      e.preventDefault();
      e.stopPropagation();
      const card = btn.closest('details.cmd');
      const parts = [];
      card.querySelectorAll('pre').forEach(pre => {
        if (!pre.classList.contains('empty')) parts.push(pre.textContent);
      });
      const text = parts.join('\\n');
      if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(text).then(() => showCopied(btn)).catch(() => fallbackCopy(text, btn));
      } else {
        fallbackCopy(text, btn);
      }
    });
  });
</script>
</body>
</html>
"""


def render_command_artifacts_html(entries: list[dict], title: str) -> str:
    """Render command artifact entries into a self-contained HTML page.

    Args:
        entries: Records with command, stdout, stderr, and exit_code keys.
        title: Label shown in the page header.

    Returns:
        str: Full HTML document.
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
