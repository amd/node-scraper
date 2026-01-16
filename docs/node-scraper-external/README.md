# node-scraper external plugins (example)

This directory lives at **`/docs/node-scraper-external`** in the `node-scraper` repo and contains
an example external plugin package that demonstrates how to create plugins for node-scraper.

## Overview

External plugins are discovered by node-scraper via **Python entry points**. This allows plugins
to be distributed as separate packages and automatically discovered when installed.

## Installation

Use the same Python environment as `node-scraper`.

```bash
cd ~/node-scraper
source venv/bin/activate
pip install -e ./docs/node-scraper-external
```

This installs `ext-nodescraper-plugins` in editable mode and registers the plugin entry points.

## Verify Plugin Discovery

Check that node-scraper discovered the external plugin:

```bash
node-scraper run-plugins -h
```

You should see `SamplePlugin` listed alongside built-in plugins.

## Run the Example Plugin

```bash
node-scraper run-plugins SamplePlugin
```

## How It Works

### Entry Points

Plugins are registered in `pyproject.toml` using entry points:

```toml
[project.entry-points."nodescraper.plugins"]
SamplePlugin = "ext_nodescraper_plugins.sample.sample_plugin:SamplePlugin"
```

When you install the package, Python registers these entry points in the package metadata.
Node-scraper automatically discovers and loads plugins from the `nodescraper.plugins` entry point group.

### Plugin Structure

```
/docs/node-scraper-external
├─ pyproject.toml              # Package metadata + entry points
└─ ext_nodescraper_plugins/    # Plugin package
   └─ sample/                   # Plugin module
      ├─ __init__.py
      ├─ sample_plugin.py       # Plugin class
      ├─ sample_collector.py    # Data collector
      ├─ sample_analyzer.py     # Data analyzer
      └─ sample_data.py         # Data model
```

## Creating Your Own External Plugins

### Step 1: Create Package Structure

```bash
mkdir my-plugin-package
cd my-plugin-package
mkdir -p ext_nodescraper_plugins/my_plugin
```

### Step 2: Create pyproject.toml

```toml
[project]
name = "my-plugin-package"
version = "0.1.0"
requires-python = ">=3.10"
dependencies = ["amd-node-scraper"]

[project.entry-points."nodescraper.plugins"]
MyPlugin = "ext_nodescraper_plugins.my_plugin:MyPlugin"

[build-system]
requires = ["setuptools", "wheel"]
build-backend = "setuptools.build_meta"
```

### Step 3: Implement Your Plugin

Create `ext_nodescraper_plugins/my_plugin/__init__.py`:

```python
from nodescraper.base import InBandDataPlugin, InBandDataCollector
from pydantic import BaseModel

class MyDataModel(BaseModel):
    """Your data model"""
    data: dict

class MyCollector(InBandDataCollector[MyDataModel, None]):
    """Your data collector"""
    DATA_MODEL = MyDataModel

    def collect_data(self, args=None):
        # Collection logic
        return MyDataModel(data={})

class MyPlugin(InBandDataPlugin[MyDataModel, None, None]):
    """Your plugin"""
    DATA_MODEL = MyDataModel
    COLLECTOR = MyCollector
```

### Step 4: Install and Test

```bash
pip install -e .
node-scraper run-plugins -h  # Should show MyPlugin
node-scraper run-plugins MyPlugin
```

## Adding More Plugins to This Package

To add additional plugins to this example package:

1. **Create a new module** under `ext_nodescraper_plugins/`
2. **Register the entry point** in `pyproject.toml`:
   ```toml
   [project.entry-points."nodescraper.plugins"]
   SamplePlugin = "ext_nodescraper_plugins.sample.sample_plugin:SamplePlugin"
   AnotherPlugin = "ext_nodescraper_plugins.another:AnotherPlugin"
   ```
3. **Reinstall** to register the new entry point:
   ```bash
   pip install -e . --force-reinstall --no-deps
   ```
