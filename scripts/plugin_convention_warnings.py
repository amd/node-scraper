#!/usr/bin/env python3
"""Static checks for nodescraper plugin conventions.

Emits warnings to stderr for:
  - *collector* / *analyzer* modules: string command class attributes must be named
    CMD or with the CMD_ prefix (framework attrs like DATA_MODEL are skipped).
  - *collector_args.py* / *analyzer_args.py*: each field in *Args classes must use
    pydantic Field(...) with a non-empty description= for CLI help and docs.

Always exits 0 so pre-commit never blocks commits; violations are advisory only.
"""

from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parent.parent / "nodescraper" / "plugins"

# Class-level names in collectors/analyzers that are not shell-command strings.
_CMD_CHECK_SKIP_NAMES = frozenset(
    {
        "AMD_SMI_EXE",
        "DATA_MODEL",
        "SUPPORTED_OS_FAMILY",
        "COLLECTOR",
        "ANALYZER",
        "COLLECTOR_ARGS",
        "ANALYZER_ARGS",
        "TYPE_CHECKING",
    }
)


def _is_stringish(expr: ast.expr) -> bool:
    if isinstance(expr, ast.Constant) and isinstance(expr.value, str):
        return True
    if isinstance(expr, ast.JoinedStr):
        return True
    return False


def _stringish_preview(expr: ast.expr) -> str | None:
    """Best-effort static string for command-like heuristics (f-strings may be partial)."""
    if isinstance(expr, ast.Constant) and isinstance(expr.value, str):
        return expr.value
    if isinstance(expr, ast.JoinedStr):
        parts: list[str] = []
        for elt in expr.values:
            if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
                parts.append(elt.value)
            else:
                parts.append("\x00")  # dynamic segment
        return "".join(parts) if parts else ""
    return None


def _looks_like_shell_command_literal(s: str) -> bool:
    """True if this class-level string is plausibly a shell/CLI invocation (not IDs, tokens, paths)."""
    s = s.strip()
    if not s:
        return False
    if re.fullmatch(r"0x[0-9a-fA-F]+", s):
        return False
    # OS / config tokens such as PRETTY_NAME, VERSION_ID
    if re.fullmatch(r"[A-Z][A-Z0-9_]+", s):
        return False
    # Filenames / simple paths (no shell metacharacters)
    if "." in s and not re.search(r"[\s|;&$`]", s):
        return False
    if re.search(r"[\s|;&$`<>]", s):
        return True
    # Typical one-word inband commands: uptime, sysctl, dmesg, amd-smi, etc.
    if re.fullmatch(r"[a-z][a-z0-9_.-]*", s, flags=re.IGNORECASE):
        return True
    return False


def _base_name(node: ast.expr) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Subscript):
        return _base_name(node.value)
    if isinstance(node, ast.Attribute):
        return node.attr
    return None


def _is_collector_or_analyzer_class(cls: ast.ClassDef) -> bool:
    return cls.name.endswith("Collector") or cls.name.endswith("Analyzer")


def _field_call_name(func: ast.expr) -> bool:
    if isinstance(func, ast.Name) and func.id == "Field":
        return True
    if isinstance(func, ast.Attribute) and func.attr == "Field":
        return True
    return False


def _field_has_nonempty_description(call: ast.Call) -> bool:
    for kw in call.keywords:
        if kw.arg != "description" or kw.value is None:
            continue
        v = kw.value
        if isinstance(v, ast.Constant) and isinstance(v.value, str) and v.value.strip():
            return True
    return False


def _check_cmd_prefixes(path: Path, tree: ast.Module) -> list[str]:
    msgs: list[str] = []
    for node in tree.body:
        # Keeps only classes whose names end with Collector or Analyzer (e.g. ProcessCollector, PcieAnalyzer).
        if not isinstance(node, ast.ClassDef) or not _is_collector_or_analyzer_class(node):
            continue
        for stmt in node.body:
            if not isinstance(stmt, ast.Assign) or len(stmt.targets) != 1:
                continue
            t = stmt.targets[0]
            if not isinstance(t, ast.Name):
                continue
            name = t.id
            if name.startswith("_") or name in _CMD_CHECK_SKIP_NAMES:
                continue
            if not _is_stringish(stmt.value):
                continue
            preview = _stringish_preview(stmt.value)
            if preview is None or not _looks_like_shell_command_literal(preview):
                continue
            if name == "CMD" or name.startswith("CMD_"):
                continue
            msgs.append(
                f"{path}:{stmt.lineno}: [{node.name}] command-like class attribute {name!r} "
                "should be renamed to CMD or to start with CMD_."
            )
    return msgs


def _is_args_class(cls: ast.ClassDef) -> bool:
    if not cls.name.endswith("Args"):
        return False
    if not cls.bases:
        return False
    for b in cls.bases:
        bn = _base_name(b)
        if bn in ("BaseModel", "CollectorArgs", "AnalyzerArgs"):
            return True
        if bn and bn.endswith("Args"):
            return True
    return False


def _annotation_mentions_classvar(ann: ast.expr | None) -> bool:
    if ann is None:
        return False
    if isinstance(ann, ast.Name) and ann.id == "ClassVar":
        return True
    if isinstance(ann, ast.Subscript):
        return _annotation_mentions_classvar(ann.value)
    if isinstance(ann, ast.Attribute) and ann.attr == "ClassVar":
        return True
    if isinstance(ann, ast.BinOp) and isinstance(ann.op, ast.BitOr):
        return _annotation_mentions_classvar(ann.left) or _annotation_mentions_classvar(ann.right)
    return False


def _check_args_fields(path: Path, tree: ast.Module) -> list[str]:
    msgs: list[str] = []
    for node in tree.body:
        if not isinstance(node, ast.ClassDef) or not _is_args_class(node):
            continue
        for stmt in node.body:
            if isinstance(stmt, ast.AnnAssign):
                if _annotation_mentions_classvar(stmt.annotation):
                    continue
                if not isinstance(stmt.target, ast.Name):
                    continue
                field_name = stmt.target.id
                if field_name.startswith("_") or field_name in ("model_config",):
                    continue
                if stmt.value is None:
                    msgs.append(
                        f"{path}:{stmt.lineno}: [{node.name}] {field_name}: "
                        "use Field(..., description='...') for every Args field."
                    )
                    continue
                if isinstance(stmt.value, ast.Call) and _field_call_name(stmt.value.func):
                    if not _field_has_nonempty_description(stmt.value):
                        msgs.append(
                            f"{path}:{stmt.lineno}: [{node.name}] {field_name}: "
                            "Field(...) must include a non-empty description= for help text."
                        )
                else:
                    msgs.append(
                        f"{path}:{stmt.lineno}: [{node.name}] {field_name}: "
                        "must assign pydantic Field(...) with description=."
                    )
            elif isinstance(stmt, ast.Assign) and len(stmt.targets) == 1:
                t = stmt.targets[0]
                if not isinstance(t, ast.Name):
                    continue
                field_name = t.id
                if field_name.startswith("_") or field_name in ("model_config",):
                    continue
                val = stmt.value
                if isinstance(val, ast.Call) and _field_call_name(val.func):
                    if not _field_has_nonempty_description(val):
                        msgs.append(
                            f"{path}:{stmt.lineno}: [{node.name}] {field_name}: "
                            "Field(...) must include a non-empty description= for help text."
                        )
    return msgs


def main() -> None:
    if not PLUGIN_ROOT.is_dir():
        sys.stderr.write(f"warning: plugins directory not found: {PLUGIN_ROOT}\n")
        return

    all_msgs: list[str] = []
    for path in sorted(PLUGIN_ROOT.rglob("*.py")):
        rel = path.relative_to(PLUGIN_ROOT.parent.parent)
        name = path.name
        try:
            src = path.read_text(encoding="utf-8")
            tree = ast.parse(src, filename=str(path))
        except (OSError, SyntaxError) as e:
            all_msgs.append(f"{rel}: could not parse: {e}")
            continue

        if "collector" in name and name.endswith(".py"):
            all_msgs.extend(_check_cmd_prefixes(rel, tree))
        if "analyzer" in name and name.endswith(".py"):
            all_msgs.extend(_check_cmd_prefixes(rel, tree))

        if name == "collector_args.py" or name == "analyzer_args.py":
            all_msgs.extend(_check_args_fields(rel, tree))

    if all_msgs:
        sys.stderr.write("plugin convention warnings (commit not blocked):\n")
        for m in all_msgs:
            sys.stderr.write(f"  WARNING: {m}\n")
    else:
        # Match the style of hooks like mypy ("Success: no issues found") for clean runs.
        sys.stdout.write("Success: no plugin convention warnings (commit not blocked).\n")
    sys.exit(0)


if __name__ == "__main__":
    main()
