"""Target for memray: build a PluginRegistry in eager or lazy mode and optionally resolve plugins.

Run through ``run_memray.sh`` (or directly: ``memray run -o out.bin scripts/memray/registry_target.py --mode lazy``).
"""

import argparse
import sys

from nodescraper.pluginregistry import PluginRegistry


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["eager", "lazy"], required=True)
    parser.add_argument(
        "--plugin",
        action="append",
        default=[],
        help="Plugin name to resolve after building the registry (repeatable). "
        "Simulates a run that only uses these plugins.",
    )
    args = parser.parse_args()

    registry = PluginRegistry(lazy_load=args.mode == "lazy")
    for name in args.plugin:
        registry.plugins[name]

    plugin_modules = sum(
        1 for m in sys.modules if m.startswith("nodescraper.plugins.") and m.count(".") >= 3
    )
    sys.stdout.write(
        f"mode={args.mode} plugins_listed={len(registry.plugins)} "
        f"plugin_modules_imported={plugin_modules} total_modules={len(sys.modules)}\n"
    )


if __name__ == "__main__":
    main()
