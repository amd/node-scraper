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
  --package /home/alexbara/node-scraper/nodescraper/plugins/inband \
  --output PLUGIN_DOC.md
"""
import argparse
import importlib
import inspect
import os
import pkgutil
import sys
from pathlib import Path
from typing import Any, Iterable, List, Optional, Type

LINK_BASE_DEFAULT = "https://github.com/amd/node-scraper/blob/HEAD/"
REL_ROOT_DEFAULT = "nodescraper/plugins/inband"
DEFAULT_ROOT_PACKAGE = "nodescraper.plugins"


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

    # Extract analyzer args if provided
    if inspect.isclass(args_cls):
        anns = get_attr(args_cls, "__annotations__", {}) or {}
        if anns:
            output.append("**Analyzer Args:**")
            for key, value in anns.items():
                # Format the type annotation
                type_str = str(value).replace("typing.", "")
                output.append(f"- `{key}`: {type_str}")

    return output


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


def annotations_for_model(model_cls: type) -> List[str]:
    anns = get_attr(model_cls, "__annotations__", {}) or {}
    return [f"**{k}**: `{v}`" for k, v in anns.items()]


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
            out.append(f"**{name}**: `{val}`")
    return out


def generate_plugin_table_rows(plugins: List[type]) -> List[List[str]]:
    rows = []
    for p in plugins:
        dm = get_attr(p, "DATA_MODEL", None)
        col = get_attr(p, "COLLECTOR", None)
        an = get_attr(p, "ANALYZER", None)
        args = get_attr(p, "ANALYZER_ARGS", None)
        cmds = []
        if inspect.isclass(col):
            cmds += extract_cmds_from_classvars(col)
            seen = set()
            uniq = []
            for c in cmds:
                key = " ".join(c.split())
                if key not in seen:
                    seen.add(key)
                    uniq.append(c)
            cmds = uniq

        # Extract regexes and args from analyzer
        regex_and_args = []
        if inspect.isclass(an):
            regex_and_args = extract_regexes_and_args_from_analyzer(an, args)

        rows.append(
            [
                p.__name__,
                "<br>".join(cmds).replace("|", "\\|") if cmds else "-",
                "<br>".join(regex_and_args).replace("|", "\\|") if regex_and_args else "-",
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

    exclude = {"__doc__", "__module__", "__weakref__", "__dict__"}
    cv = class_vars_dump(col, exclude)
    if cv:
        s += md_header("Class Variables", 3) + md_list(cv)

    dm = get_attr(col, "DATA_MODEL", None)
    s += md_header("Provides Data", 3) + (f"{dm.__name__}\n\n" if inspect.isclass(dm) else "-\n\n")

    cmds = []
    cmds += extract_cmds_from_classvars(col)
    if cmds:
        seen, uniq = set(), []
        for c in cmds:
            key = " ".join(c.split())
            if key not in seen:
                seen.add(key)
                uniq.append(c)
        cmds = uniq
        s += md_header("Commands", 3) + md_list(cmds)

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

    exclude = {"__doc__", "__module__", "__weakref__", "__dict__"}
    cv = class_vars_dump(an, exclude)
    if cv:
        s += md_header("Class Variables", 3) + md_list(cv)

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

    anns = get_attr(args_cls, "__annotations__", {}) or {}
    if anns:
        ann_items = [f"**{k}**: `{v}`" for k, v in anns.items()]
        s += md_header("Annotations / fields", 3) + md_list(ann_items)
    return s


def main():
    ap = argparse.ArgumentParser(
        description="Generate Plugin Table and detail sections with setup_link + rel-root."
    )
    ap.add_argument(
        "--package", default=DEFAULT_ROOT_PACKAGE, help="Dotted package or filesystem path"
    )
    ap.add_argument("--output", default="PLUGIN_DOC.md", help="Output Markdown file")
    args = ap.parse_args()

    root = args.package
    root_path = Path(root)
    if os.sep in root or root_path.exists():
        root = dotted_from_path(root_path)
    base = find_inband_plugin_base()
    import_all_modules(root)

    def all_subclasses(cls: Type) -> set[type]:
        seen, out, work = set(), set(), [cls]
        while work:
            parent = work.pop()
            for sub in parent.__subclasses__():
                if sub not in seen:
                    seen.add(sub)
                    out.add(sub)
                    work.append(sub)
        return out

    plugins = [c for c in all_subclasses(base) if c is not base]
    plugins = [c for c in plugins if not get_attr(c, "__abstractmethods__", set())]
    plugins.sort(key=lambda c: f"{c.__module__}.{c.__name__}".lower())

    rows = generate_plugin_table_rows(plugins)
    headers = [
        "Plugin",
        "Collection",
        "Analysis",
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
    out.append(md_header("Plugin Table", 1))
    out.append(render_table(headers, rows))

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

    Path(args.output).write_text("".join(out), encoding="utf-8")


if __name__ == "__main__":
    main()
