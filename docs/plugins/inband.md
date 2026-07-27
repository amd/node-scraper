# In-band plugins

In-band plugins run on the **host OS** (local shell or SSH). They inherit `InBandDataPlugin` and `InBandDataCollector`.

## Base classes

| Class | Role |
| --- | --- |
| `InBandDataPlugin` | Sets `CONNECTION_TYPE = InBandConnectionManager` |
| `InBandDataCollector` | `_run_sut_cmd()`, `_read_sut_file()` on target |
| `RegexAnalyzer` | Common pattern for log-based analyzers |

Source: `nodescraper/base/__init__.py`, `nodescraper/base/inbandcollectortask.py`

## Connection

- **LOCAL** — no connection config; commands run on the machine where `node-scraper` is installed.
- **REMOTE** — `--connection-config` with `InBandConnectionManager` (SSH).

See [../connections/connection-config.md](../connections/connection-config.md).

## Example plugins

| Plugin | Collects |
| --- | --- |
| `DmesgPlugin` | Kernel ring buffer |
| `RocmPlugin` | ROCm/SMI version and health |
| `PciePlugin` | PCIe topology |
| `MemoryPlugin` | DIMM / memory errors |
| `ScaleOutAristaPlugin` | Switch CLI (in-band SSH to switch) |

Full list: [../PLUGIN_DOC.md](../PLUGIN_DOC.md) (In-band section).

## Minimal plugin shape

```python
from nodescraper.base import InBandDataPlugin, InBandDataCollector

class MyCollector(InBandDataCollector[MyDataModel, MyCollectorArgs]):
    DATA_MODEL = MyDataModel

    def collect_data(self, args=None):
        output = self._run_sut_cmd("my_command")
        return MyDataModel(raw=output)

class MyPlugin(InBandDataPlugin[MyDataModel, MyCollectorArgs, MyAnalyzerArgs]):
    DATA_MODEL = MyDataModel
    COLLECTOR = MyCollector
    ANALYZER = MyAnalyzer
```

## Related

- [../architecture/overview.md](../architecture/overview.md)
- [../node-scraper-external/README.md](../node-scraper-external/README.md) — external plugin packaging
- [../../EXTENDING.md](../../EXTENDING.md) — programmatic API
