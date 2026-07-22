#!/usr/bin/env python3
"""Checks conventions under ``nodescraper/plugins`` (stderr warnings only; non-blocking).

1. **Command strings in collectors/analyzers** , for  ``Collector``
   or ``Analyzer`` classes: a *class-level* assignment to a string (or f-string) that
   looks like a shell/CLI invocation must use the name ``CMD`` or
   ``CMD_<suffix>`` (e.g. ``CMD_LIST``). Names starting with ``_`` and names
   listed in ``_CMD_CHECK_SKIP_NAMES`` are ignored; see
   ``_looks_like_shell_command_literal`` for what counts as command-like.

2. **Args models** — In ``collector_args.py`` and ``analyzer_args.py``,
   for classes named ``*Args`` that subclass ``BaseModel``, ``CollectorArgs``,
   ``AnalyzerArgs``, or another ``*Args``: each public field should assign
   ``pydantic.Field(...)`` with a non-empty ``description=`` (for help/CLI
   text). ``ClassVar`` fields, ``_``-prefixed names, and ``model_config`` are
   skipped.

3. **Shell quoting** — In ``Collector`` / ``Analyzer`` methods, values from
   ``args.*``, ``cmd_spec.*``, or sensitive function parameters (names ending
   in ``_path`` / ``_file``, or ``url``, ``boot``, ``folder``, ``host``) that
   are interpolated into shell commands (``_run_sut_cmd``, ``_run_amd_smi``,
   ``_run_dell_command``) must be wrapped in ``shell_quote(...)`` or assigned
   from a prior ``shell_quote(...)`` call in the same function.
   ``GenericCollectionCollector`` is excluded (user commands are intentional).
"""

from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
PLUGIN_ROOT = _REPO_ROOT / "nodescraper" / "plugins"

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

_SHELL_RUN_METHODS = frozenset({"_run_sut_cmd", "_run_amd_smi", "_run_dell_command"})
_SKIP_SHELL_QUOTE_CLASSES = frozenset({"GenericCollectionCollector"})


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
    """Rule #1: warn when a command-like class attr is not ``CMD`` / ``CMD_*``."""
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
    """Rule #2: warn when Args fields lack ``Field`` with a non-empty ``description``."""
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


def _is_shell_quote_call(expr: ast.expr) -> bool:
    if not isinstance(expr, ast.Call):
        return False
    func = expr.func
    if isinstance(func, ast.Name) and func.id == "shell_quote":
        return True
    return isinstance(func, ast.Attribute) and func.attr == "shell_quote"


def _func_param_names(func: ast.FunctionDef | ast.AsyncFunctionDef) -> set[str]:
    names: set[str] = set()
    for arg in func.args.args + func.args.kwonlyargs:
        if arg.arg != "self":
            names.add(arg.arg)
    if func.args.vararg:
        names.add(func.args.vararg.arg)
    return names


def _collect_shell_quote_safe_names(func: ast.FunctionDef | ast.AsyncFunctionDef) -> set[str]:
    safe: set[str] = set()
    for node in ast.walk(func):
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if isinstance(target, ast.Name) and _is_shell_quote_call(node.value):
                safe.add(target.id)
    return safe


def _expr_preview(expr: ast.expr) -> str:
    try:
        return ast.unparse(expr)
    except Exception:
        return "<expr>"


def _is_sensitive_param_name(name: str) -> bool:
    if name in {"url", "boot", "folder", "hostname", "host"}:
        return True
    return name.endswith("_path") or name.endswith("_file")


def _is_user_controlled_leaf(expr: ast.expr, param_names: set[str]) -> bool:
    if isinstance(expr, ast.Attribute) and isinstance(expr.value, ast.Name):
        base = expr.value.id
        if base in ("args", "cmd_spec"):
            return True
    if isinstance(expr, ast.Name) and expr.id in param_names:
        return _is_sensitive_param_name(expr.id)
    return False


def _contains_user_controlled(expr: ast.expr, param_names: set[str]) -> bool:
    if _is_user_controlled_leaf(expr, param_names):
        return True
    for child in ast.iter_child_nodes(expr):
        if isinstance(child, ast.expr) and _contains_user_controlled(child, param_names):
            return True
    return False


def _is_trivially_safe_expr(expr: ast.expr, safe_names: set[str]) -> bool:
    if _is_shell_quote_call(expr):
        return True
    if isinstance(expr, ast.Constant):
        return True
    if isinstance(expr, ast.Name) and expr.id in safe_names:
        return True
    if isinstance(expr, ast.Attribute) and isinstance(expr.value, ast.Name):
        base = expr.value.id
        if base == "self" and (
            expr.attr == "CMD" or expr.attr.startswith("CMD_") or expr.attr in ("AMD_SMI_EXE",)
        ):
            return True
    return False


def _command_insert_issues(
    expr: ast.expr,
    param_names: set[str],
    safe_names: set[str],
) -> list[tuple[int, str]]:
    issues: list[tuple[int, str]] = []

    def note(value: ast.expr) -> None:
        if _is_trivially_safe_expr(value, safe_names):
            return
        if _contains_user_controlled(value, param_names):
            issues.append((getattr(value, "lineno", 0), _expr_preview(value)))

    if isinstance(expr, ast.JoinedStr):
        for part in expr.values:
            if isinstance(part, ast.FormattedValue):
                note(part.value)
    elif isinstance(expr, ast.Call) and isinstance(expr.func, ast.Attribute):
        if expr.func.attr == "format":
            for kw in expr.keywords:
                if kw.arg is not None and kw.value is not None:
                    note(kw.value)
    elif isinstance(expr, ast.BinOp):
        note(expr.left)
        note(expr.right)

    return issues


def _resolve_command_exprs(
    func: ast.FunctionDef | ast.AsyncFunctionDef, expr: ast.expr
) -> list[ast.expr]:
    if not isinstance(expr, ast.Name):
        return [expr]

    matches: list[ast.expr] = []
    for node in ast.walk(func):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == expr.id:
                    matches.append(node.value)
        elif (
            isinstance(node, ast.AnnAssign)
            and isinstance(node.target, ast.Name)
            and node.target.id == expr.id
            and node.value is not None
        ):
            matches.append(node.value)
    return matches or [expr]


def _check_function_shell_quoting(
    path: Path,
    class_name: str,
    func: ast.FunctionDef | ast.AsyncFunctionDef,
) -> list[str]:
    msgs: list[str] = []
    param_names = _func_param_names(func)
    safe_names = _collect_shell_quote_safe_names(func)

    for node in ast.walk(func):
        if not isinstance(node, ast.Call):
            continue
        if not isinstance(node.func, ast.Attribute):
            continue
        if node.func.attr not in _SHELL_RUN_METHODS:
            continue
        if not node.args:
            continue

        command_expr = node.args[0]
        for resolved in _resolve_command_exprs(func, command_expr):
            for lineno, preview in _command_insert_issues(resolved, param_names, safe_names):
                line = lineno or node.lineno
                msgs.append(
                    f"{path}:{line}: [{class_name}.{func.name}] user-controlled value "
                    f"{preview} in shell command must use shell_quote(...)."
                )
    return msgs


def _check_shell_quoting(path: Path, tree: ast.Module) -> list[str]:
    """Rule #3: warn when config/param values reach shell commands without shell_quote."""
    msgs: list[str] = []
    for node in tree.body:
        if not isinstance(node, ast.ClassDef) or not _is_collector_or_analyzer_class(node):
            continue
        if node.name in _SKIP_SHELL_QUOTE_CLASSES:
            continue
        for stmt in node.body:
            if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)):
                msgs.extend(_check_function_shell_quoting(path, node.name, stmt))
    return msgs


def main() -> None:
    if not PLUGIN_ROOT.is_dir():
        sys.stderr.write(f"warning: plugins directory not found: {PLUGIN_ROOT}\n")
        return

    all_msgs: list[str] = []
    for path in sorted(PLUGIN_ROOT.rglob("*.py")):
        rel = path.relative_to(_REPO_ROOT)
        name = path.name
        try:
            src = path.read_text(encoding="utf-8")
            tree = ast.parse(src, filename=str(path))
        except (OSError, SyntaxError) as e:
            all_msgs.append(f"{rel}: could not parse: {e}")
            continue

        if "collector" in name and name.endswith(".py"):
            all_msgs.extend(_check_cmd_prefixes(rel, tree))
            all_msgs.extend(_check_shell_quoting(rel, tree))
        if "analyzer" in name and name.endswith(".py"):
            all_msgs.extend(_check_cmd_prefixes(rel, tree))
            all_msgs.extend(_check_shell_quoting(rel, tree))

        if name == "collector_args.py" or name == "analyzer_args.py":
            all_msgs.extend(_check_args_fields(rel, tree))

    if all_msgs:
        sys.stderr.write("plugin convention warnings (commit not blocked):\n")
        for m in all_msgs:
            sys.stderr.write(f"  WARNING: {m}\n")
    else:
        sys.stdout.write("Success: no plugin convention warnings.\n")
    sys.exit(0)


if __name__ == "__main__":
    main()
