# node-scraper external plugins (example)

This directory lives at **`/docs/node-scraper-external`** in the `node-scraper` repo and contains
an example external plugin package you can install in editable mode.

## Installation

Use the same Python environment as `node-scraper`.

```bash
cd ~/node-scraper
pip install -e ./docs/node-scraper-external
```
You should see `ext-nodescraper-plugins` installed in editable mode.


## Verify the external package is importable

```bash
python - <<'PY'
import ext_nodescraper_plugins
print("ext_nodescraper_plugins loaded from:", ext_nodescraper_plugins.__file__)
PY
```

## Run external plugins

Confirm the CLI sees your external plugin(s):

```bash
node-scraper run-plugins -h
node-scraper run-plugins SamplePlugin
```

## Add your own plugins

Add new modules under the **`ext_nodescraper_plugins/`** package. Example layout:

```
/docs/node-scraper-external
├─ pyproject.toml
└─ ext_nodescraper_plugins/
   ├─ __init__.py
   └─ sample/
      ├─ __init__.py
      └─ sample_plugin.py
```

```

Re-install (editable mode picks up code changes automatically, but if you add new files you may
need to re-run):
```bash
pip install -e .
```
