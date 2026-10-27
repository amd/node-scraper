#!/usr/bin/env bash
# Compare memory use of the old (eager) and new (--lazy-load) plugin loading with memray,
# running the real node-scraper CLI.
#
# Usage: scripts/memray/run_memray.sh
#
# Override the invocation with env vars (defaults match a typical quanta run):
#   CONNECTION_CONFIG  path to the connection config JSON
#   SYS_NAME, SYS_LOCATION, SYS_SKU, SYS_PLATFORM
#   PLUGINS            plugin name(s) passed to run-plugins (default: OsPlugin)
#   OUT_DIR            output directory (default: ./memray_out)
#
# Registry-only comparison (no connection needed):
#   memray run -o out.bin scripts/memray/registry_target.py --mode {eager|lazy} --plugin OsPlugin
#
# Requires: pip install memray
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
OUT_DIR="${OUT_DIR:-$PWD/memray_out}"
CONNECTION_CONFIG="${CONNECTION_CONFIG:-/home/graepaul/dev_trees/ns/connection-config_quanta-ccs-aus-f15-40.json}"
SYS_NAME="${SYS_NAME:-quanta}"
SYS_LOCATION="${SYS_LOCATION:-REMOTE}"
SYS_SKU="${SYS_SKU:-MI325}"
SYS_PLATFORM="${SYS_PLATFORM:-quanta}"
PLUGINS="${PLUGINS:-OsPlugin}"

mkdir -p "$OUT_DIR"
export PYTHONPATH="$REPO_ROOT${PYTHONPATH:+:$PYTHONPATH}"

# node-scraper --sys-name quanta [--lazy-load] --sys-location REMOTE --sys-sku MI325 \
#   --sys-platform quanta --connection-config <file> run-plugins OsPlugin
run_cli_args() {
  local lazy_flag=("$@")
  echo --sys-name "$SYS_NAME" "${lazy_flag[@]}" \
    --sys-location "$SYS_LOCATION" --sys-sku "$SYS_SKU" --sys-platform "$SYS_PLATFORM" \
    --connection-config "$CONNECTION_CONFIG" run-plugins $PLUGINS
}

for mode in eager lazy; do
  # Pin NODESCRAPER_LAZY_LOAD per mode so a value exported in the caller's shell cannot
  # turn the eager (old) run lazy.
  lazy_flag=()
  lazy_env=0
  if [ "$mode" = lazy ]; then
    lazy_flag=(--lazy-load)
    lazy_env=1
  fi
  bin="$OUT_DIR/cli-$mode.bin"
  rm -f "$bin"
  echo "=== $mode (NODESCRAPER_LAZY_LOAD=$lazy_env) ==="
  # shellcheck disable=SC2046
  env NODESCRAPER_LAZY_LOAD="$lazy_env" \
    python3 -m memray run --force -o "$bin" -m nodescraper.cli.cli $(run_cli_args "${lazy_flag[@]}")
  python3 -m memray flamegraph --force -o "$OUT_DIR/cli-$mode-flamegraph.html" "$bin"
  python3 -m memray stats "$bin" > "$OUT_DIR/cli-$mode-stats.txt"
done

echo
echo "Peak memory:"
for mode in eager lazy; do
  printf '  %-6s ' "$mode"
  grep -m1 -iE "peak memory" "$OUT_DIR/cli-$mode-stats.txt" || echo "n/a (see $OUT_DIR/cli-$mode-stats.txt)"
done
echo "Flamegraphs: $OUT_DIR/cli-{eager,lazy}-flamegraph.html"
echo "Side-by-side: python3 -m memray summary $OUT_DIR/cli-eager.bin; python3 -m memray summary $OUT_DIR/cli-lazy.bin"
