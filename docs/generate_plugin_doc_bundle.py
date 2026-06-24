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
"""
Usage
python generate_plugin_doc_bundle.py \
  --output docs/PLUGIN_DOC.md \
  --update-readme-help
"""
import argparse
import importlib
import inspect
import os
import pkgutil
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Iterable, List, Optional, Type

LINK_BASE_DEFAULT = "https://github.com/amd/node-scraper/blob/HEAD/"
REL_ROOT_DEFAULT = "nodescraper/plugins"
# Import and document every concrete plugin under nodescraper.plugins (inband, ooband,
# generic_collection, regex_search, serviceability, …).
PACKAGE_PLUGINS_ROOT = "nodescraper.plugins"
# ``plugins_for_package_prefix`` matches on ``cls.__module__``; keep the trailing dot so
# ``nodescraper.plugins`` itself does not match every module starting with that string.
PLUGIN_MODULE_PREFIX = f"{PACKAGE_PLUGINS_ROOT}."
DEFAULT_PACKAGES = (PACKAGE_PLUGINS_ROOT,)


def get_attr(obj: Any, name: str, default: Any = None) -> Any:
    try:
        return getattr(obj, name)
    except Exception:
        return default


def _slice_from_rel_root(p: Path, rel_root: Optional[str]) -> Optional[str]:
    if not rel_root:
        return None
    parts = list(p.parts)
    target = [seg for seg in Path(rel_root).parts if seg not in ("/", "\\")]
    if not target:
        return None
    for i in range(0, len(parts) - len(target) + 1):
        if parts[i : i + len(target)] == target:
            return "/".join(parts[i:])
    return None


def setup_link(class_data, link_base: str, rel_root: Optional[str]) -> str:
    try:
        file_location = Path(inspect.getfile(class_data)).resolve()
    except Exception:
        return "-"
    rel_path = _slice_from_rel_root(file_location, rel_root)
    if rel_path is None:
        try:
            rel_path = str(
                file_location.relative_to(Path(__file__).parent.parent.resolve())
            ).replace("\\", "/")
        except Exception:
            rel_path = file_location.name
    base = (link_base or "").rstrip("/") + "/"
    return base + rel_path


def get_own_doc(cls: type) -> Optional[str]:
    """
    Return only the __doc__ defined in the class itself, ignore inheritance.
    """
    try:
        raw = cls.__dict__.get("__doc__", None)
        if raw is None:
            return None
        return str(raw).strip()
    except Exception:
        return None


def sanitize_doc(doc: str) -> str:
    if not doc:
        return doc
    lines = doc.splitlines()
    out = []
    in_attr_block = False
    for raw in lines:
        line = raw.rstrip("\n")
        stripped = line.strip()
        if stripped.startswith('!!! abstract "Usage Documentation"'):
            continue
        if stripped.startswith("[Models](") and "concepts/models" in stripped:
            continue
        if stripped == "A base class for creating Pydantic models.":
            continue
        if stripped == "Attributes:":
            in_attr_block = True
            continue
        if in_attr_block:
            if (
                stripped.startswith("__pydantic_")
                or stripped.startswith("__signature__")
                or stripped.startswith("__class_vars__")
                or stripped.startswith("__private_attributes__")
                or stripped == ""
                or raw.startswith(" ")
                or raw.startswith("\t")
            ):
                continue
            in_attr_block = False
        if (
            stripped.startswith("__pydantic_")
            or stripped.startswith("__signature__")
            or stripped.startswith("__class_vars__")
            or stripped.startswith("__private_attributes__")
        ):
            continue
        out.append(line)
    return "\n".join(out).strip()


def find_pkg_root_from_path(path: Path) -> Path:
    p = path.resolve()
    if p.is_file():
        p = p.parent
    last_pkg = p
    cur = p
    while (cur / "__init__.py").exists():
        last_pkg = cur
        cur = cur.parent
    return last_pkg


def dotted_from_path(path: Path) -> str:
    path = path.resolve()
    pkg_root = find_pkg_root_from_path(path)
    sys.path.insert(0, str(pkg_root.parent))
    rel = path.relative_to(pkg_root.parent)
    parts = list(rel.parts)
    if parts[-1].endswith(".py"):
        parts[-1] = parts[-1][:-3]
    return ".".join(parts)


def iter_modules(package_name: str) -> Iterable[str]:
    pkg = importlib.import_module(package_name)
    yield package_name
    if hasattr(pkg, "__path__"):
        for mod in pkgutil.walk_packages(pkg.__path__, prefix=pkg.__name__ + "."):
            yield mod.name


def import_all_modules(package_name: str) -> None:
    for modname in iter_modules(package_name):
        try:
            importlib.import_module(modname)
        except Exception:
            pass


def find_inband_plugin_base():
    base_mod = importlib.import_module("nodescraper.base")
    return get_attr(base_mod, "InBandDataPlugin")


def find_oob_plugin_bases() -> tuple[type, ...]:
    """Return OOB plugin base classes (Redfish + BMC SSH) used to discover OOB plugins."""
    base_mod = importlib.import_module("nodescraper.base")
    oob = get_attr(base_mod, "OOBandDataPlugin")
    oob_ssh = get_attr(base_mod, "OOBSSHDataPlugin")
    bases = [b for b in (oob, oob_ssh) if b is not None]
    return tuple(bases)


def is_concrete_plugin_class(cls: type) -> bool:
    if not inspect.isclass(cls):
        return False
    return not bool(get_attr(cls, "__abstractmethods__", set()))


def all_subclasses_union(bases: Iterable[type]) -> set[type]:
    """All distinct concrete descendants across one or more base classes (transitive)."""
    merged: set[type] = set()
    for base in bases:
        merged |= all_subclasses_single(base)
    return merged


def all_subclasses_single(cls: type) -> set[type]:
    seen, out, work = set(), set(), [cls]
    while work:
        parent = work.pop()
        for sub in parent.__subclasses__():
            if sub not in seen:
                seen.add(sub)
                out.add(sub)
                work.append(sub)
    return out


def plugins_for_package_prefix(base_classes: Iterable[type], package_prefix: str) -> List[type]:
    """Non-abstract plugin classes under ``base_classes`` whose ``__module__`` starts with *package_prefix*."""
    found: List[type] = []
    for cls in all_subclasses_union(base_classes):
        mod = getattr(cls, "__module__", "") or ""
        if not mod.startswith(package_prefix):
            continue
        if not is_concrete_plugin_class(cls):
            continue
        found.append(cls)
    return found


def link_anchor(obj: Any, kind: str) -> str:
    if obj is None or not inspect.isclass(obj):
        return "-"
    name = obj.__name__
    if kind == "model":
        return f"[{name}](#{name}-Model)"
    if kind == "collector":
        return f"[{name}](#Collector-Class-{name})"
    if kind == "analyzer":
        return f"[{name}](#Data-Analyzer-Class-{name})"
    if kind == "args":
        return name
    return name


def extract_cmds_from_classvars(collector_cls: type) -> List[str]:
    if not inspect.isclass(collector_cls):
        return []
    cmds: List[str] = []
    seen = set()
    for attr in dir(collector_cls):
        if not attr.startswith("CMD"):
            continue
        val = get_attr(collector_cls, attr, default=None)
        if val is None:
            continue

        def add_cmd(s: Any):
            if not isinstance(s, str):
                return
            norm = " ".join(s.split())
            if norm not in seen:
                seen.add(norm)
                cmds.append(s)

        if isinstance(val, dict):
            for item in val.values():
                add_cmd(item)
        elif isinstance(val, (list, tuple)):
            for item in val:
                add_cmd(item)
        else:
            add_cmd(val)
    return cmds


# Optional human-readable bullets for plugins without CMD_* shell snippets (e.g. Redfish).
DOCUMENTATION_COLLECTION_ITEMS_ATTR = "DOCUMENTATION_COLLECTION_ITEMS"
DOCUMENTATION_ANALYSIS_ITEMS_ATTR = "DOCUMENTATION_ANALYSIS_ITEMS"


def _documentation_lines_for_attr(cls: Any, attr_name: str) -> List[str]:
    if cls is None or not inspect.isclass(cls):
        return []
    raw = get_attr(cls, attr_name, None)
    if raw is None:
        return []
    if isinstance(raw, str):
        return [ln.strip() for ln in raw.splitlines() if ln.strip()]
    if isinstance(raw, (list, tuple)):
        return [str(x).strip() for x in raw if isinstance(x, str) and str(x).strip()]
    return []


def merge_unique_lines(*line_groups: Iterable[str]) -> List[str]:
    """Concatenate line groups, dropping exact duplicates while preserving order."""
    seen: set[str] = set()
    out: List[str] = []
    for group in line_groups:
        for line in group:
            if line not in seen:
                seen.add(line)
                out.append(line)
    return out


def extract_collection_lines_for_table(plugin_cls: type, collector_cls: Any) -> List[str]:
    """Shell CMD_* lines plus optional DOCUMENTATION_COLLECTION_ITEMS (collector then plugin)."""
    cmd_lines: List[str] = []
    if inspect.isclass(collector_cls):
        cmd_lines = extract_cmds_from_classvars(collector_cls)
    doc_collector = _documentation_lines_for_attr(
        collector_cls, DOCUMENTATION_COLLECTION_ITEMS_ATTR
    )
    doc_plugin = _documentation_lines_for_attr(plugin_cls, DOCUMENTATION_COLLECTION_ITEMS_ATTR)
    return merge_unique_lines(cmd_lines, doc_collector, doc_plugin)


def extract_analysis_doc_lines_for_table(plugin_cls: type, analyzer_cls: Any) -> List[str]:
    """Optional DOCUMENTATION_ANALYSIS_ITEMS (analyzer then plugin) for the analyzer column."""
    doc_an = _documentation_lines_for_attr(analyzer_cls, DOCUMENTATION_ANALYSIS_ITEMS_ATTR)
    doc_pl = _documentation_lines_for_attr(plugin_cls, DOCUMENTATION_ANALYSIS_ITEMS_ATTR)
    return merge_unique_lines(doc_an, doc_pl)


def iter_plugin_collector_classes(plugin_cls: type) -> List[type]:
    """Return collector class(es) for a plugin (supports tuple COLLECTOR via DataPlugin.get_collector_classes)."""
    gcs = getattr(plugin_cls, "get_collector_classes", None)
    if callable(gcs):
        try:
            return [c for c in gcs() if inspect.isclass(c)]
        except Exception:
            return []
    return []


def collector_has_table_collection_coverage(plugin_cls: type, collector_cls: type) -> bool:
    """True if the plugin table Collection cell would be non-empty from CMD_* or documentation lines."""
    if extract_cmds_from_classvars(collector_cls):
        return True
    if _documentation_lines_for_attr(collector_cls, DOCUMENTATION_COLLECTION_ITEMS_ATTR):
        return True
    if _documentation_lines_for_attr(plugin_cls, DOCUMENTATION_COLLECTION_ITEMS_ATTR):
        return True
    return False


def analyzer_has_table_analysis_coverage(
    plugin_cls: type, analyzer_cls: type, analyzer_args_cls: Any
) -> bool:
    """True if the Analyzer Args table cell would be non-empty from regex/args extraction or doc lines."""
    if _documentation_lines_for_attr(analyzer_cls, DOCUMENTATION_ANALYSIS_ITEMS_ATTR):
        return True
    if _documentation_lines_for_attr(plugin_cls, DOCUMENTATION_ANALYSIS_ITEMS_ATTR):
        return True
    if extract_regexes_and_args_from_analyzer(analyzer_cls, analyzer_args_cls):
        return True
    return False


def collect_plugin_doc_table_coverage_messages(plugins: List[type]) -> List[str]:
    """Messages for plugins whose generated table would show '-' for collection or analysis unjustifiably."""
    msgs: List[str] = []
    for p in plugins:
        pname = p.__name__
        for c in iter_plugin_collector_classes(p):
            if not collector_has_table_collection_coverage(p, c):
                msgs.append(
                    f"{pname}: collector {c.__name__} has no CMD_* command strings and no "
                    f"{DOCUMENTATION_COLLECTION_ITEMS_ATTR} on the collector or plugin."
                )
        an = get_attr(p, "ANALYZER", None)
        aargs = get_attr(p, "ANALYZER_ARGS", None)
        if inspect.isclass(an) and not analyzer_has_table_analysis_coverage(p, an, aargs):
            msgs.append(
                f"{pname}: analyzer {an.__name__} has no extractable analyzer table content "
                f"(built-in regexes / *REGEX* attrs / analyzer args fields) and no "
                f"{DOCUMENTATION_ANALYSIS_ITEMS_ATTR} on the analyzer or plugin."
            )
    return msgs


def emit_plugin_doc_coverage_warnings(msgs: List[str], *, strict: bool) -> None:
    if not msgs:
        return
    sys.stderr.write("PLUGIN_DOC.md table coverage warnings:\n")
    for m in msgs:
        sys.stderr.write(f"  WARNING: {m}\n")
    if strict:
        sys.stderr.write(
            f"error: {len(msgs)} plugin documentation coverage warning(s) "
            "(--strict-plugin-doc-coverage)\n"
        )
        sys.exit(1)


def extract_regexes_and_args_from_analyzer(
    analyzer_cls: type, args_cls: Optional[type]
) -> List[str]:
    """Extract regex patterns and analyzer args from analyzer class"""
    if not inspect.isclass(analyzer_cls):
        return []

    output: List[str] = []

    # Check for ERROR_REGEX class variable (used by RegexAnalyzer subclasses like DmesgAnalyzer)
    error_regex = get_attr(analyzer_cls, "ERROR_REGEX", None)
    if error_regex and isinstance(error_regex, list):
        output.append("**Built-in Regexes:**")
        for item in error_regex:
            # ErrorRegex objects have regex, message, event_category attributes
            if hasattr(item, "regex"):
                pattern = getattr(item.regex, "pattern", None)
                message = getattr(item, "message", "")
                if pattern:
                    # Truncate long patterns
                    pattern_str = pattern if len(pattern) < 50 else pattern[:47] + "..."
                    output.append(f"- {message}: `{pattern_str}`")
            elif hasattr(item, "pattern"):
                pattern_str = item.pattern if len(item.pattern) < 50 else item.pattern[:47] + "..."
                output.append(f"- `{pattern_str}`")

    # Check for other regex-related attributes
    for attr in dir(analyzer_cls):
        if "REGEX" in attr.upper() and not attr.startswith("_"):
            val = get_attr(analyzer_cls, attr, default=None)
            if val is None or attr == "ERROR_REGEX":
                continue

            if hasattr(val, "pattern"):
                output.append(f"**{attr}**: `{val.pattern}`")
            elif isinstance(val, str):
                output.append(f"**{attr}**: `{val}`")

    # Extract analyzer args if provided (prefer model_fields for descriptions)
    if inspect.isclass(args_cls):
        fields = get_attr(args_cls, "model_fields", None)
        if fields and isinstance(fields, dict):
            output.append("**Analyzer Args:**")
            for key in fields:
                try:
                    finfo = fields[key]
                    ann = getattr(finfo, "annotation", None)
                    type_str = format_type_annotation(ann) if ann is not None else "Any"
                    line = f"- `{key}`: {type_str}"
                    desc = get_field_description(
                        finfo, for_table=True, model_cls=args_cls, field_name=key
                    )
                    if desc:
                        line += f" — {desc}"
                    output.append(line)
                except Exception:
                    pass
        else:
            anns = get_attr(args_cls, "__annotations__", {}) or {}
            if anns:
                output.append("**Analyzer Args:**")
                for key, value in anns.items():
                    type_str = format_type_annotation(value)
                    output.append(f"- `{key}`: {type_str}")

    return output


def extract_collection_args_from_collector_args(args_cls: Optional[type]) -> List[str]:
    """Extract collector/collection args from collector args class for the plugin table."""
    if not inspect.isclass(args_cls):
        return []
    output: List[str] = []
    # Prefer model_fields for Pydantic models (includes inherited); fallback to __annotations__
    fields = get_attr(args_cls, "model_fields", None)
    if fields and isinstance(fields, dict):
        # Pydantic v2: model_fields is a dict of field names -> FieldInfo
        for key in fields:
            try:
                finfo = fields[key]
                ann = getattr(finfo, "annotation", None)
                type_str = format_type_annotation(ann) if ann is not None else "Any"
                line = f"- `{key}`: {type_str}"
                desc = get_field_description(
                    finfo, for_table=True, model_cls=args_cls, field_name=key
                )
                if desc:
                    line += f" — {desc}"
                output.append(line)
            except Exception:
                pass
    if not output:
        anns = get_attr(args_cls, "__annotations__", {}) or {}
        for key, value in anns.items():
            type_str = format_type_annotation(value)
            output.append(f"- `{key}`: {type_str}")
    if output:
        output.insert(0, "**Collection Args:**")
    return output


def escape_table_cell(s: str) -> str:
    """Escape content for a markdown table cell so pipes and newlines don't break columns.
    Use HTML entity for pipe so all markdown parsers treat it as content, not column separator.
    """
    if not s:
        return s
    # Avoid @ in cells (e.g. OData property names) being turned into mail/mention links in Outlook/HTML viewers.
    return s.replace("|", "&#124;").replace("@", "&#64;").replace("\n", " ").replace("\r", " ")


def md_header(text: str, level: int = 2) -> str:
    return f"{'#' * level} {text}\n\n"


def md_kv(key: str, value: str) -> str:
    return f"**{key}**: {value}\n\n"


def md_list(items: List[str]) -> str:
    return "".join(f"- {i}\n" for i in items) + ("\n" if items else "")


def bases_list(cls: type) -> List[str]:
    try:
        return [b.__name__ for b in cls.__bases__]
    except Exception:
        return []


def format_type_annotation(type_ann: Any) -> str:
    """
    Format a type annotation for documentation, removing non-deterministic content like function memory addresses.
    """
    import re

    type_str = str(type_ann)
    type_str = type_str.replace("typing.", "")
    type_str = re.sub(r"<function\s+(\w+)\s+at\s+0x[0-9a-fA-F]+>", r"\1", type_str)
    type_str = re.sub(r"<bound method\s+(\S+)\s+of\s+.+?>", r"\1", type_str)
    type_str = re.sub(r"<class '([^']+)'>", r"\1", type_str)
    return type_str


def get_field_description(
    finfo: Any,
    for_table: bool = False,
    max_len: Optional[int] = 120,
    model_cls: Optional[Type] = None,
    field_name: Optional[str] = None,
) -> Optional[str]:
    """Get description from a Pydantic FieldInfo. If for_table, single-line and escape pipes.
    Falls back to model JSON schema description when model_cls and field_name are provided.
    """
    desc = getattr(finfo, "description", None)
    if (not desc or not isinstance(desc, str)) and model_cls and field_name:
        try:
            schema = model_cls.model_json_schema()
            desc = schema.get("properties", {}).get(field_name, {}).get("description")
        except Exception:
            pass
    if not desc or not isinstance(desc, str):
        return None
    desc = desc.strip()
    if not desc:
        return None
    if for_table:
        desc = desc.replace("\n", " ").replace("|", "\\|")
        if max_len and len(desc) > max_len:
            desc = desc[: max_len - 3].rstrip() + "..."
    return desc


def annotations_for_model(model_cls: type) -> List[str]:
    anns = get_attr(model_cls, "__annotations__", {}) or {}
    return [f"**{k}**: `{format_type_annotation(v)}`" for k, v in anns.items()]


def format_class_var_value(val: Any) -> str:
    """Stable string for docs. set/frozenset repr order depends on PYTHONHASHSEED."""
    if isinstance(val, frozenset):
        if not val:
            return "frozenset()"
        items = sorted(val, key=lambda x: (type(x).__name__, repr(x)))
        return "frozenset({" + ", ".join(repr(x) for x in items) + "})"
    if isinstance(val, set):
        if not val:
            return "set()"
        items = sorted(val, key=lambda x: (type(x).__name__, repr(x)))
        return "{" + ", ".join(repr(x) for x in items) + "}"
    return str(val)


def class_vars_dump(cls: type, exclude: set) -> List[str]:
    ignore = {"abc_impl", "_abc_impl", "__abstractmethods__"}
    exclude = set(exclude) | ignore
    out = []
    for name, val in vars(cls).items():
        if name.startswith("__") or name in exclude:
            continue
        if callable(val) or isinstance(val, (staticmethod, classmethod, property)):
            continue

        # Format list values with each item on a new line
        if isinstance(val, list) and len(val) > 0:
            val_str = str(val)
            if len(val_str) > 200:
                formatted_items = []
                for item in val:
                    formatted_items.append(f"  {item}")
                formatted_list = "[\n" + ",\n".join(formatted_items) + "\n]"
                out.append(f"**{name}**: `{formatted_list}`")
            else:
                out.append(f"**{name}**: `{val}`")
        else:
            out.append(f"**{name}**: `{format_class_var_value(val)}`")
    return out


def generate_plugin_table_rows(plugins: List[type]) -> List[List[str]]:
    rows = []
    for p in plugins:
        dm = get_attr(p, "DATA_MODEL", None)
        col = get_attr(p, "COLLECTOR", None)
        an = get_attr(p, "ANALYZER", None)
        args = get_attr(p, "ANALYZER_ARGS", None)
        collector_args_cls = get_attr(p, "COLLECTOR_ARGS", None)
        cmds = extract_collection_lines_for_table(p, col)

        # Extract regexes and args from analyzer; optional DOCUMENTATION_ANALYSIS_* lines first
        regex_and_args: List[str] = extract_analysis_doc_lines_for_table(
            p, an if inspect.isclass(an) else None
        )
        if inspect.isclass(an):
            regex_and_args.extend(extract_regexes_and_args_from_analyzer(an, args))

        # Extract collection args from collector args class
        collection_args_lines = extract_collection_args_from_collector_args(collector_args_cls)

        rows.append(
            [
                p.__name__,
                escape_table_cell("<br>".join(cmds)) if cmds else "-",
                escape_table_cell("<br>".join(regex_and_args)) if regex_and_args else "-",
                (
                    escape_table_cell("<br>".join(collection_args_lines))
                    if collection_args_lines
                    else "-"
                ),
                link_anchor(dm, "model") if inspect.isclass(dm) else "-",
                link_anchor(col, "collector") if inspect.isclass(col) else "-",
                link_anchor(an, "analyzer") if inspect.isclass(an) else "-",
            ]
        )
    return rows


def render_table(headers: List[str], rows: List[List[str]]) -> str:
    out = []
    out.append("| " + " | ".join(headers) + " |\n")
    out.append("| " + " | ".join("---" for _ in headers) + " |\n")
    for r in rows:
        out.append("| " + " | ".join(r) + " |\n")
    out.append("\n")
    return "".join(out)


def render_collector_section(col: type, link_base: str, rel_root: Optional[str]) -> str:
    hdr = md_header(f"Collector Class {col.__name__}", 2)
    desc = sanitize_doc(get_own_doc(col) or "")
    s = hdr
    if desc:
        s += md_header("Description", 3) + desc + "\n\n"
    s += md_kv("Bases", str(bases_list(col)))
    _url = setup_link(col, link_base, rel_root)
    s += md_kv("Link to code", f"[{Path(_url).name}]({_url})")

    exclude = {
        "__doc__",
        "__module__",
        "__weakref__",
        "__dict__",
        DOCUMENTATION_COLLECTION_ITEMS_ATTR,
    }
    cv = class_vars_dump(col, exclude)
    if cv:
        s += md_header("Class Variables", 3) + md_list(cv)

    dm = get_attr(col, "DATA_MODEL", None)
    s += md_header("Provides Data", 3) + (f"{dm.__name__}\n\n" if inspect.isclass(dm) else "-\n\n")

    cmds = extract_cmds_from_classvars(col)
    if cmds:
        s += md_header("Commands", 3) + md_list(cmds)

    doc_coll = _documentation_lines_for_attr(col, DOCUMENTATION_COLLECTION_ITEMS_ATTR)
    if doc_coll:
        s += md_header("Documented collection", 3) + md_list(doc_coll)

    return s


def render_analyzer_section(an: type, link_base: str, rel_root: Optional[str]) -> str:
    hdr = md_header(f"Data Analyzer Class {an.__name__}", 2)
    desc = sanitize_doc(get_own_doc(an) or "")
    s = hdr
    if desc:
        s += md_header("Description", 3) + desc + "\n\n"
    s += md_kv("Bases", str(bases_list(an)))
    _url = setup_link(an, link_base, rel_root)
    s += md_kv("Link to code", f"[{Path(_url).name}]({_url})")

    exclude = {
        "__doc__",
        "__module__",
        "__weakref__",
        "__dict__",
        DOCUMENTATION_ANALYSIS_ITEMS_ATTR,
    }
    cv = class_vars_dump(an, exclude)
    if cv:
        s += md_header("Class Variables", 3) + md_list(cv)

    doc_an = _documentation_lines_for_attr(an, DOCUMENTATION_ANALYSIS_ITEMS_ATTR)
    if doc_an:
        s += md_header("Documented analysis", 3) + md_list(doc_an)

    # Add regex patterns if present (pass None for args_cls since we don't have context here)
    regex_info = extract_regexes_and_args_from_analyzer(an, None)
    if regex_info:
        s += md_header("Regex Patterns", 3)
        if len(regex_info) > 10:
            s += f"*{len(regex_info)} items defined*\n\n"
        s += md_list(regex_info)

    return s


def render_model_section(model: type, link_base: str, rel_root: Optional[str]) -> str:
    hdr = md_header(f"{model.__name__} Model", 2)
    desc = sanitize_doc(get_own_doc(model) or "")
    s = hdr
    if desc:
        s += md_header("Description", 3) + desc + "\n\n"
    _url = setup_link(model, link_base, rel_root)
    s += md_kv("Link to code", f"[{Path(_url).name}]({_url})")
    s += md_kv("Bases", str(bases_list(model)))
    anns = annotations_for_model(model)
    if anns:
        s += md_header("Model annotations and fields", 3) + md_list(anns)
    return s


def render_analyzer_args_section(args_cls: type, link_base: str, rel_root: Optional[str]) -> str:
    hdr = md_header(f"Analyzer Args Class {args_cls.__name__}", 2)
    desc = sanitize_doc(get_own_doc(args_cls) or "")
    s = hdr
    if desc:
        s += md_header("Description", 3) + desc + "\n\n"
    s += md_kv("Bases", str(bases_list(args_cls)))
    _url = setup_link(args_cls, link_base, rel_root)
    s += md_kv("Link to code", f"[{Path(_url).name}]({_url})")

    fields = get_attr(args_cls, "model_fields", None)
    if fields and isinstance(fields, dict):
        ann_items = []
        for k in fields:
            try:
                finfo = fields[k]
                ann = getattr(finfo, "annotation", None)
                type_str = format_type_annotation(ann) if ann is not None else "Any"
                item = f"**{k}**: `{type_str}`"
                field_desc = get_field_description(
                    finfo, for_table=False, model_cls=args_cls, field_name=k
                )
                if field_desc:
                    item += f" — {field_desc}"
                ann_items.append(item)
            except Exception:
                ann = getattr(fields[k], "annotation", None)
                ann_items.append(
                    f"**{k}**: `{format_type_annotation(ann) if ann is not None else 'Any'}`"
                )
        if ann_items:
            s += md_header("Annotations / fields", 3) + md_list(ann_items)
    else:
        anns = get_attr(args_cls, "__annotations__", {}) or {}
        if anns:
            ann_items = [f"**{k}**: `{format_type_annotation(v)}`" for k, v in anns.items()]
            s += md_header("Annotations / fields", 3) + md_list(ann_items)
    return s


# Markers in README.md that bracket the node-scraper -h block (HTML comments, not rendered).
README_HELP_BLOCK_START = "<!-- node-scraper -h start -->"
README_HELP_BLOCK_END = "<!-- node-scraper -h end -->"


def update_readme_help(readme_path: Path) -> bool:
    """
    Update the node-scraper -h output block in README.md.
    The block must be wrapped with <!-- node-scraper -h start --> and <!-- node-scraper -h end -->.
    """
    result = subprocess.run(
        [sys.executable, "-m", "nodescraper.cli.cli", "-h"],
        capture_output=True,
        text=True,
        cwd=readme_path.parent,
    )
    if result.returncode != 0:
        return False
    help_text = result.stdout.strip()
    # Redact hostname in --sys-name default so README does not show machine name
    help_text = re.sub(
        r"(--sys-name STRING\s+System name \(default: )\S+",
        r"\g<1><current hostname>)",
        help_text,
    )
    content = readme_path.read_text(encoding="utf-8")
    start_idx = content.find(README_HELP_BLOCK_START)
    end_idx = content.find(README_HELP_BLOCK_END)
    if start_idx == -1 or end_idx == -1 or end_idx <= start_idx:
        return False
    # Replace the entire bracketed block (from start marker through end marker)
    block_end = end_idx + len(README_HELP_BLOCK_END)
    new_block = f"{README_HELP_BLOCK_START}\n```sh\n{help_text}\n```\n{README_HELP_BLOCK_END}"
    new_content = content[:start_idx] + new_block + content[block_end:]
    readme_path.write_text(new_content, encoding="utf-8")
    return True


def main():
    # Prefer loading plugins from repo root so Field descriptions are picked up
    _repo_root = Path(__file__).resolve().parent.parent
    if str(_repo_root) not in sys.path:
        sys.path.insert(0, str(_repo_root))

    ap = argparse.ArgumentParser(
        description="Generate Plugin Table and detail sections with setup_link + rel-root."
    )
    ap.add_argument(
        "--package",
        action="append",
        dest="packages",
        default=None,
        metavar="PKG",
        help=(
            "Dotted package or filesystem path to import in addition to the default plugin "
            f"packages ({', '.join(DEFAULT_PACKAGES)}). Repeatable."
        ),
    )
    ap.add_argument(
        "--output",
        default="docs/PLUGIN_DOC.md",
        help="Output Markdown file (default: docs/PLUGIN_DOC.md under repo root)",
    )
    ap.add_argument(
        "--update-readme-help",
        action="store_true",
        help="Update the node-scraper -h output block in README.md (run from repo root or with correct cwd)",
    )
    ap.add_argument(
        "--readme",
        default=None,
        help="Path to README.md (default: README.md in current working directory)",
    )
    ap.add_argument(
        "--strict-plugin-doc-coverage",
        action="store_true",
        help=(
            "Exit with status 1 if any plugin lacks CMD_* / DOCUMENTATION_COLLECTION_ITEMS "
            "for collectors or lacks analyzer table content / DOCUMENTATION_ANALYSIS_ITEMS "
            "when an analyzer is defined."
        ),
    )
    args = ap.parse_args()

    normalized_extra: List[str] = []
    if args.packages:
        for root in args.packages:
            root_path = Path(root)
            if os.sep in root or root_path.exists():
                root = dotted_from_path(root_path)
            normalized_extra.append(root)

    # Always import the full nodescraper.plugins tree; append optional extras.
    to_import: List[str] = []
    seen_pkg: set[str] = set()
    for pkg in list(DEFAULT_PACKAGES) + normalized_extra:
        if pkg not in seen_pkg:
            seen_pkg.add(pkg)
            to_import.append(pkg)

    for pkg in to_import:
        import_all_modules(pkg)

    inband_base = find_inband_plugin_base()
    oob_bases = find_oob_plugin_bases()

    ib_plugins = sorted(
        plugins_for_package_prefix((inband_base,), PLUGIN_MODULE_PREFIX),
        key=lambda c: f"{c.__module__}.{c.__name__}".lower(),
    )
    oob_plugins = sorted(
        plugins_for_package_prefix(oob_bases, PLUGIN_MODULE_PREFIX),
        key=lambda c: f"{c.__module__}.{c.__name__}".lower(),
    )
    plugins = sorted(
        set(ib_plugins) | set(oob_plugins),
        key=lambda c: f"{c.__module__}.{c.__name__}".lower(),
    )

    coverage_msgs = collect_plugin_doc_table_coverage_messages(plugins)
    emit_plugin_doc_coverage_warnings(coverage_msgs, strict=args.strict_plugin_doc_coverage)

    ib_rows = generate_plugin_table_rows(ib_plugins)
    oob_rows = generate_plugin_table_rows(oob_plugins)
    headers = [
        "Plugin",
        "Collection",
        "Analyzer Args",
        "Collection Args",
        "DataModel",
        "Collector",
        "Analyzer",
    ]

    collectors, analyzers, models, args_classes = [], [], [], []
    seen_c, seen_a, seen_m, seen_args = set(), set(), set(), set()
    for p in plugins:
        col = get_attr(p, "COLLECTOR", None)
        an = get_attr(p, "ANALYZER", None)
        dm = get_attr(p, "DATA_MODEL", None)
        ar = get_attr(p, "ANALYZER_ARGS", None)
        if inspect.isclass(col) and col not in seen_c:
            seen_c.add(col)
            collectors.append(col)
        if inspect.isclass(an) and an not in seen_a:
            seen_a.add(an)
            analyzers.append(an)
        if inspect.isclass(dm) and dm not in seen_m:
            seen_m.add(dm)
            models.append(dm)
        if inspect.isclass(ar) and ar not in seen_args:
            seen_args.add(ar)
            args_classes.append(ar)

    out = []
    out.append(md_header("Plugin Documentation", 1))
    out.append(md_header("IB Plugins", 1))
    out.append(render_table(headers, ib_rows))
    out.append(md_header("OOB plugins", 1))
    out.append(render_table(headers, oob_rows))

    if collectors:
        out.append(md_header("Collectors", 1))
        for c in collectors:
            out.append(render_collector_section(c, LINK_BASE_DEFAULT, REL_ROOT_DEFAULT))

    if models:
        out.append(md_header("Data Models", 1))
        for m in models:
            out.append(render_model_section(m, LINK_BASE_DEFAULT, REL_ROOT_DEFAULT))

    if analyzers:
        out.append(md_header("Data Analyzers", 1))
        for a in analyzers:
            out.append(render_analyzer_section(a, LINK_BASE_DEFAULT, REL_ROOT_DEFAULT))

    if args_classes:
        out.append(md_header("Analyzer Args", 1))
        for a in args_classes:
            out.append(render_analyzer_args_section(a, LINK_BASE_DEFAULT, REL_ROOT_DEFAULT))

    repo_root = Path(__file__).resolve().parent.parent
    output_path = Path(args.output)
    if not output_path.is_absolute():
        output_path = repo_root / output_path
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("".join(out), encoding="utf-8")

    if args.update_readme_help:
        readme_path = Path(args.readme) if args.readme else Path.cwd() / "README.md"
        if not readme_path.is_file():
            readme_path = Path(__file__).resolve().parent.parent / "README.md"
        if readme_path.is_file():
            if update_readme_help(readme_path):
                print(f"Updated node-scraper -h block in {readme_path}")  # noqa: T201
            else:
                print(f"Could not find or update -h block in {readme_path}")  # noqa: T201
                sys.exit(1)
        else:
            print(f"README not found: {readme_path}")  # noqa: T201
            sys.exit(1)


if __name__ == "__main__":
    main()
