# Performance Metrics Guide

> 🏠 **[Documentation Home](./README.md)** | 
> ⚙️ **[Configuration](./configuration-pylaunch.en.md)** | 
> 🔧 **[Hooks](./hooks-guide.en.md)** | 
> 📊 **[Dynamic Columns](./columns-guide.en.md)**

---

## 📊 Overview

ProFiles includes built-in performance monitoring for file scanning operations. When enabled, the application logs detailed metrics about each scan, helping you:

- **Monitor scan performance** over time
- **Identify bottlenecks** in large directory trees
- **Optimize configuration** (exclusions, recursive settings)
- **Track throughput** (files/second) for capacity planning

---

## 🔧 Enabling Performance Metrics

### Via Configuration File

Add the `scan_metrics` setting to your `[LAUNCHER]` section:

```ini
[LAUNCHER]
scan_metrics = Vrai
verbose = DEBUG
```

**Available values**:
- `Vrai` (or `True`, `Yes`, `1`, `On`) - Enable metrics logging
- `Faux` (or `False`, `No`, `0`, `Off`) - Disable metrics logging (default)

> **Note**: Metrics are logged at **DEBUG** level. You must set `verbose = DEBUG` to see them.

### Via Code (Programmatic API)

When using ProFiles programmatically:

```python
from profiles.core.config.models import AppConfig
from profiles.core.processing.scanner import scan_and_process

# Create config with metrics enabled
config = AppConfig(
    search_dir="/path/to/scan",
    scan_metrics=True,  # Enable metrics
    verbose="DEBUG",
)

# Scan with automatic metrics logging
results = scan_and_process(
    directory=config.search_dir,
    extension=".mttl",
    recursive=True,
    config=config,  # Pass config for automatic metrics
)
```

---

## 📈 Metrics Output

When enabled, ProFiles logs the following metrics after each scan operation:

```
DEBUG Scan metrics: {'directory': '/path/to/scan', 
                     'file_count': 150, 
                     'duration_ms': 245.6, 
                     'files_per_second': 610.7, 
                     'recursive': True, 
                     'error_count': 0}
```

### Metric Fields

| Field | Type | Description |
|-------|------|-------------|
| `directory` | string | Absolute path of the scanned directory |
| `file_count` | integer | Number of files found matching criteria |
| `duration_ms` | float | Total scan duration in milliseconds |
| `files_per_second` | float | Throughput (files processed per second) |
| `recursive` | boolean | Whether recursive scanning was enabled |
| `error_count` | integer | Number of errors encountered during scan |

---

## 🎯 Use Cases

### 1. **Performance Baseline**

Track scan performance over time to establish baselines:

```ini
[LAUNCHER]
scan_metrics = Vrai
verbose = DEBUG
```

**Example log output**:
```
2026-08-03 10:15:23 DEBUG Scan metrics: {'file_count': 150, 'duration_ms': 245.6, 'files_per_second': 610.7}
2026-08-03 10:20:45 DEBUG Scan metrics: {'file_count': 152, 'duration_ms': 251.3, 'files_per_second': 604.8}
2026-08-03 10:25:12 DEBUG Scan metrics: {'file_count': 148, 'duration_ms': 238.9, 'files_per_second': 619.5}
```

**Analysis**: Consistent performance around 600-620 files/second.

### 2. **Optimization Testing**

Test different exclusion patterns to improve scan speed:

```ini
# Before optimization
[LAUNCHER]
search_exclude_dirs = .git
scan_metrics = Vrai

# After optimization - add more exclusions
[LAUNCHER]
search_exclude_dirs = .git, __pycache__, bin, obj, tmp, Debug
scan_metrics = Vrai
```

**Compare metrics**:
- **Before**: 1500 files, 2500ms, 600 files/sec
- **After**: 800 files, 900ms, 889 files/sec (+48% improvement)

### 3. **Recursive vs Non-Recursive**

Evaluate the performance impact of recursive scanning:

```ini
# Non-recursive scan
[LAUNCHER]
recursive_search = Faux
scan_metrics = Vrai

# Recursive scan
[LAUNCHER]
recursive_search = Vrai
scan_metrics = Vrai
```

### 4. **Large Directory Monitoring**

Monitor scans of very large directory trees (10,000+ files):

```
DEBUG Scan metrics: {'directory': 'D:\\Production\\Tests', 
                     'file_count': 15420, 
                     'duration_ms': 3245.8, 
                     'files_per_second': 4751.2, 
                     'recursive': True}
```

**Insight**: ~4750 files/sec on large tree indicates healthy performance.

---

## 🔍 Troubleshooting

### Metrics Not Appearing

**Problem**: `scan_metrics = Vrai` but no metrics in logs.

**Solutions**:
1. Verify `verbose = DEBUG` is set
2. Check log file path and permissions
3. Ensure you're scanning a directory (not an empty one)

```ini
[LAUNCHER]
verbose = DEBUG
scan_metrics = Vrai
```

### Slow Scan Performance

**Symptoms**: `files_per_second` < 100

**Possible causes**:
1. **Network drive** - Scanning over network is slower
2. **Antivirus** - Real-time scanning adds overhead
3. **Too many files** - Consider exclusions
4. **Recursive scan** - Non-recursive is faster

**Recommendations**:
```ini
[LAUNCHER]
# Add aggressive exclusions
search_exclude_dirs = .git, __pycache__, bin, obj, tmp, Debug, Release, .vs
search_exclude_files = *backup*, *.tmp, ~$*, *.log

# Use non-recursive if possible
recursive_search = Faux

# Enable metrics to verify improvement
scan_metrics = Vrai
```

### High Error Count

**Problem**: `error_count` > 0 in metrics

**Possible causes**:
1. Permission denied on some directories
2. File system errors
3. Locked files

**Action**: Check logs for specific error messages and adjust permissions or exclusions.

---

## 📊 Performance Benchmarks

### Typical Performance Ranges

| Scenario | Files/Second | Notes |
|----------|--------------|-------|
| **Local SSD, small tree (<1000 files)** | 2000-5000 | Excellent performance |
| **Local SSD, medium tree (1000-10000 files)** | 1000-3000 | Good performance |
| **Local HDD, large tree (10000+ files)** | 500-1500 | Acceptable |
| **Network drive (LAN)** | 200-800 | Expected slowdown |
| **Network drive (WAN)** | 50-200 | Significant latency |

### Optimization Tips

1. **Use exclusions** - Skip unnecessary directories
2. **Non-recursive scans** - When subdirectories aren't needed
3. **Local storage** - Avoid network drives for frequent scans
4. **SSD over HDD** - Significant performance difference
5. **Close file explorers** - Prevents file locking issues

---

## 🛠️ Advanced Usage

### Programmatic Metrics Access

For custom applications, access metrics directly:

```python
from profiles.core.telemetry.metrics import ScanTimer
import logging

logger = logging.getLogger(__name__)

timer = ScanTimer("/path/to/scan", recursive=True)
timer.__enter__()

# Perform scan
results = perform_scan()

timer.record_files(len(results))
timer.__exit__(None, None, None)

# Access metrics programmatically
metrics = timer.get_metrics()
if metrics:
    logger.info(f"Scan completed: {metrics.file_count} files in {metrics.duration_ms:.2f}ms")
    logger.info(f"Throughput: {metrics.files_per_second:.2f} files/sec")
```

### Custom Logging Format

Configure custom log format to include metrics:

```python
import logging

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s %(levelname)s [%(source)s] %(message)s",
    handlers=[logging.FileHandler("profiles.log"), logging.StreamHandler()],
)
```

---

## 📚 Related Documentation

- **[Configuration Reference](./configuration-pylaunch.en.md)** - Full `.profiles` configuration guide
- **[Advanced Guide](./advanced/advanced-guide.en.md)** - CLI automation and programmatic API
- **[AGENTS.md](../AGENTS.md)** - Architecture and performance best practices

---

## 🔄 Version History

- **v2026.7.0** - Initial performance metrics implementation
- **v2026.8.0** - Added `scan_metrics` config option, integrated with GUI

---

*Last updated: 2026-08-03*
