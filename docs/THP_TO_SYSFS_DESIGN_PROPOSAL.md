# Proposal: ThpPlugin → Generic SysfsPlugin (design + copyright)

## 1. Copyright updates (implemented)

- **Rule:** New files added in 2026 must use copyright year **2026**.
- **Done:** All ThpPlugin-related files updated from `2025` to `2026`:
  - `nodescraper/plugins/inband/thp/*.py` (6 files)
  - `test/unit/plugin/test_thp_collector.py`, `test_thp_analyzer.py`

---

## 2. Design: From ThpPlugin to a generic SysfsPlugin

### 2.1 Goals (from review)

- **Generic plugin:** Rename to something like **SysfsPlugin** (or SysfsSettingsPlugin) so it can check any sysfs paths, not only THP.
- **Config-driven paths:** Collector commands and checks are driven by a list of paths (and optional expected values) from analyzer args, not hardcoded to `/sys/kernel/mm/transparent_hugepage/`.
- **Doc generation:** Use a stable `CMD` (or `CMD_<>`) variable built from the list of paths so the automated doc generator can include the commands in the docs.
- **Flexible expectations:** For each path, support an optional list of allowed values; empty list means “only check that the path exists / value is read”, no value assertion.

### 2.2 Proposed config shape (`plugin_config.json`)

```json
{
  "plugins": {
    "SysfsPlugin": {
      "analysis_args": {
        "checks": [
          {
            "path": "/sys/kernel/mm/transparent_hugepage/enabled",
            "expected": ["always", "[always]"],
            "name": "THP enabled"
          },
          {
            "path": "/sys/kernel/mm/transparent_hugepage/defrag",
            "expected": ["always", "[always]"],
            "name": "THP defrag"
          }
        ]
      }
    }
  }
}
```

- **`checks`:** List of objects, one per sysfs path.
- **`path`:** Full sysfs path (e.g. `.../enabled`, `.../defrag`).
- **`expected`:** Optional list of accepted values (e.g. raw `always` or as shown in file `[always]`). **Empty list `[]`:** do not assert value, only that the path is readable (or that we got a value).
- **`name`:** Human-readable label for logs/events (e.g. "THP enabled").

### 2.3 Data model

- **Collector output:** One structure per “check”, e.g.:
  - `path`, `value_read` (string or None if read failed), optional `name`.
- So the data model is **list-based** (one entry per path) rather than fixed fields like `enabled` / `defrag`.
- Parsing: keep support for “bracketed” sysfs format (e.g. `[always] madvise never`) and optionally store both raw and normalized value.

### 2.4 Collector behavior

- **Paths:** Build the list of paths from analyzer args (e.g. from `checks[].path`). If no analyzer args are provided, use a default list (e.g. current THP paths) so the plugin still works without config.
- **Commands:** For each path, run e.g. `cat <path>`. Define a variable so the doc generator can pick it up, e.g.:
  - `CMD_READ = "cat {}"` and document that `{}` is replaced by each path from the configured `checks`, or
  - A single `CMD` that reflects “one command per path” (e.g. “cat &lt;path&gt; for each path in analysis_args.checks”).
- **Docs:** Use a stable `CMD` / `CMD_<>` pattern as required by the existing doc generator.

### 2.5 Analyzer behavior

- For each check:
  - If `expected` is non-empty: assert `value_read` is in `expected` (after normalizing if needed).
  - If `expected` is empty: only assert that a value was read (path readable, no value check).
- Emit clear events (e.g. by `name`) on mismatch or read failure.

### 2.6 Naming and packaging

- **Plugin name:** `ThpPlugin` → **SysfsPlugin** (or SysfsSettingsPlugin).
- **Package:** Either rename `thp` → `sysfs` and keep one plugin, or keep package name and have `SysfsPlugin` live under a renamed module for clarity. Recommendation: **rename to `sysfs`** and have `SysfsPlugin`, `SysfsCollector`, `SysfsAnalyzer`, `SysfsDataModel`, `SysfsAnalyzerArgs` for consistency and future use (many sysfs paths).

### 2.7 Summary table

| Area           | Current (ThpPlugin)     | Proposed (SysfsPlugin)                          |
|----------------|------------------------|-------------------------------------------------|
| Plugin name    | ThpPlugin              | SysfsPlugin (or SysfsSettingsPlugin)           |
| Paths          | Hardcoded THP paths     | From `analysis_args.checks[].path`             |
| Expected values| Fixed `exp_enabled` / `exp_defrag` | Per-check `expected` list; `[]` = no assertion |
| Data model     | `enabled`, `defrag`    | List of `{ path, value_read, name? }`           |
| Collector CMD  | Fixed `cat` for two files | `CMD = "cat {}"` with paths from checks        |
| Copyright      | 2025                    | 2026 (done)                                     |
