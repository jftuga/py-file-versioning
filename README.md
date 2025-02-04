# py-file-versioning

A flexible file versioning system with compression support, written in Python.

**NOTE: The cli tool and API are still under development and will not be stable until v1.0.0 is released**

## Table of Contents

- [Features](#features)
- [Package Name Convention](#package-name-convention)
- [Installation](#installation)
  - [From PyPI](#from-pypi)
  - [From Source](#from-source)
  - [Command Line Usage](#command-line-usage)
  - [Demo Shell Session](#demo-shell-session)
  - [Python API Usage](#python-api-usage)
- [Configuration Options](#configuration-options)
  - [FileVersioningConfig Parameters](#fileversioningconfig-parameters)
  - [Command Line Options](#command-line-options)
- [Examples](#examples)
  - [Maintaining Multiple Versions](#maintaining-multiple-versions)
  - [Using Different Compression Types](#using-different-compression-types)
  - [Version File Naming](#version-file-naming)
- [Development](#development)
  - [Setting Up Development Environment](#setting-up-development-environment)
  - [Running Tests](#running-tests)
  - [Code Quality Checks](#code-quality-checks)
- [License](#license)

## Features

* Create versioned backups of files with automatic sequence numbering
* Multiple compression options: gzip, bzip2, xz, or uncompressed
* Configurable timestamp formats (UTC or local time)
* Limit the number of versions kept per file
* Command-line interface for easy integration
* Support for Unicode filenames
* Cross-platform compatibility

## Package Name Convention

While the package is installed as `py-file-versioning` (using hyphens), you should use `py_file_versioning` (using underscores) in your Python imports following Python naming conventions.

## Installation

### From PyPI

```bash
pip install py-file-versioning
```

### From Source

```bash
git clone https://github.com/jftuga/py-file-versioning.git
cd py-file-versioning
pip install .
```

For development installation:

```bash
uv venv
source .venv/bin/activate
uv pip install -e '.[dev]'
uv pip list
```

### Command Line Usage

The package installs a command-line tool called `pyfileversioning`. Here are some common operations:

Create a version:
```bash
pyfileversioning create myfile.txt
```

Create a compressed version:
```bash
pyfileversioning create myfile.txt -c gz  # or --compression gz
```

List all versions:
```bash
pyfileversioning list myfile.txt
```

Restore a specific version to a new file path:
```bash
pyfileversioning restore versions/myfile--20240120.123456_001.txt.gz --target /path/to/restored_file.txt
```

Remove a version:
```bash
pyfileversioning remove versions/myfile--20240120.123456_001.txt.gz
```

### Demo Shell Session

Here's a practical demonstration of using the command-line interface:

```bash
# Create a sample config file
$ echo "database_host=localhost" > config.ini
$ cat config.ini
database_host=localhost

# Create first version (uncompressed)
$ pyfileversioning create config.ini -d backups
Created version: backups/config--20250207.044841_001--loc_mod.ini

# Update the file content
$ echo "database_port=5432" >> config.ini

# Create compressed version
$ pyfileversioning create config.ini -d backups -c gz
Created version: backups/config--20250207.044924_001--loc_mod.ini.gz

# List all versions
$ pyfileversioning list config.ini -d backups
Path                                        | Sequence | Size | Timestamp           | TimeZone | TimestampSrc
====                                        | ======== | ==== | =========           | ======== | ============
config--20250207.044924_001--loc_mod.ini.gz |        1 |   95 | 2025-02-07T04:49:24 |    local |  modify time
config--20250207.044841_001--loc_mod.ini    |        1 |   24 | 2025-02-07T04:48:41 |    local |  modify time

# Add more content and create another version with UTC time
$ echo "database_name=myapp" >> config.ini
$ pyfileversioning create config.ini -d backups -c gz -u
Created version: backups/config--20250207.095009_001--utc_mod.ini.gz

# View all versions with size and timestamp (note: mixed timezone versions not recommended)
$ pyfileversioning list config.ini -d backups
Path                                        | Sequence | Size | Timestamp           | TimeZone | TimestampSrc
====                                        | ======== | ==== | =========           | ======== | ============
config--20250207.095009_001--utc_mod.ini.gz |        1 |  107 | 2025-02-07T09:50:09 |      utc |  modify time
config--20250207.044924_001--loc_mod.ini.gz |        1 |   95 | 2025-02-07T04:49:24 |    local |  modify time
config--20250207.044841_001--loc_mod.ini    |        1 |   24 | 2025-02-07T04:48:41 |    local |  modify time
```

### Python API Usage

The library provides a flexible API for file versioning. Here's how to use it:

```python
from py_file_versioning import FileVersioning, FileVersioningConfig

# Create a test file
def create_example_file(filename: str) -> None:
    content = """
    # Database configuration settings
    db_host = db.example.com
    db_port = 5432
    db_name = production_db
    """.strip()
    with open(filename, 'w') as f:
        f.write(content)

# Basic usage
filename = "example.ini"
create_example_file(filename)

versioning = FileVersioning()
version_path, removed, error = versioning.create_version(filename)
if error:
    print(f"Warning: {error}")
print(version_path)

# Advanced configuration
config = FileVersioningConfig(
    versions_path="backups",     # Store versions in 'backups' directory
    compression="gz",            # Use gzip compression
    max_versions=5,             # Keep only last 5 versions
    use_utc=True,              # Use UTC timestamps
    use_modified_time=True,    # Use file's modified time
    delimiter="__"             # Custom delimiter for version files
)
versioning = FileVersioning(config)
version_path, removed, error = versioning.create_version(filename)
if error:
    print(f"Warning: {error}")
print(version_path)
```

## Configuration Options

### FileVersioningConfig Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| delimiter | str | "--" | Separator between filename and version information |
| use_utc | bool | False | Use UTC timestamps instead of local time |
| versions_path | str | "versions" | Directory to store versions |
| compression | str | "none" | Compression type: "none", "gz", "bz2", "xz" |
| max_versions | Optional[int] | None | Maximum number of versions to keep |
| use_modified_time | bool | True | Use file's modified time instead of current time |

### Command Line Options

```
usage: pyfileversioning [-h] [-V] [-t TARGET] [-d VERSIONS_PATH]
                        [-c {none,gz,bz2,xz}] [-m MAX_VERSIONS] [-s {mod,sto}]
                        [-u] [-D DELIMITER]
                        [{create,restore,list,remove}] files [files ...]
```

Options:
* `-V, --version`: Show version information
* `-t, --target`: Target file path for restore operation (must be full path to the restored file)
* `-d, --versions-path`: Directory to store versions (default: versions)
* `-c, --compression`: Compression type to use (none, gz, bz2, xz)
* `-m, --max-versions`: Maximum number of versions to keep
* `-s, --src`: Source for timestamps (mod: file modified time, sto: current time)
* `-u, --utc`: Use UTC timezone for timestamps (default: local time)
* `--delimiter DELIMITER`: The delimiter to use (default: --)

Environment Variables:
* `PFV_VERSIONS_PATH`: Override default versions directory
* `PFV_COMPRESSION`: Override default compression type
* `PFV_DELIMITER`: Override default delimiter

Notes:
* The tool supports file patterns (e.g., `*.txt`, `config*.ini`)
* Multiple files can be specified for batch operations

## Examples

### Maintaining Multiple Versions

```python
from py_file_versioning import FileVersioning, FileVersioningConfig

# Create versions with different timezone and timestamp combinations
configs = [
    # Local timezone versions
    {"use_utc": False, "use_modified_time": True, "desc": "local timezone, modified time"},
    {"use_utc": False, "use_modified_time": False, "desc": "local timezone, current time"},

    # UTC timezone versions
    {"use_utc": True, "use_modified_time": True, "desc": "UTC timezone, modified time"},
    {"use_utc": True, "use_modified_time": False, "desc": "UTC timezone, current time"}
]

for cfg in configs:
    config = FileVersioningConfig(
        use_utc=cfg["use_utc"],
        use_modified_time=cfg["use_modified_time"]
    )
    versioning = FileVersioning(config)
    version_path, removed, error = versioning.create_version("example.ini")
    print(version_path)
```

### Using Different Compression Types

```python
from py_file_versioning import FileVersioning, FileVersioningConfig

# Create versions using each compression type
compression_types = ["gz", "bz2", "xz"]

for compression in compression_types:
    config = FileVersioningConfig(
        compression=compression,
        use_utc=True,          # Use UTC time
        use_modified_time=True # Use file's modified time
    )
    versioning = FileVersioning(config)
    version_path, removed, error = versioning.create_version("example.ini")
    print(version_path)
```

### Version File Naming

Version files follow this naming pattern:
```
{original_name}{delimiter}{timestamp}_{sequence}{delimiter}{version_spec}{extension}[.compression_ext]
```

Example:
```
myfile--20240120.123456_001--utc_mod.txt.gz
```

Where:
- `myfile` is the original filename
- `--` is the delimiter (configurable)
- `20240120.123456` is the timestamp (YYYYMMDD.HHMMSS)
- `001` is the sequence number
- `utc_mod` is the version specification:
  - First part (`utc` or `loc`) indicates timezone (UTC or local)
  - Second part (`mod` or `sto`) indicates timestamp source (modified time or stored/current time)
- `.txt` is the original extension
- `.gz` is the compression extension (if compression is used)

Note: All versions of a file must use consistent timezone and timestamp source settings.

## Development

### Setting Up Development Environment

```bash
# Clone the repository
git clone https://github.com/jftuga/py-file-versioning.git
cd py-file-versioning

# Create and activate virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install development dependencies
pip install -e '.[dev]'
```

### Running Tests

```bash
pytest
```

For coverage report:
```bash
pytest --cov=file_versioning --cov-report=html
```

### Code Quality Checks

```bash
# Format code
black .

# Sort imports
isort .

# Style checking
flake8

# Linting
ruff check
```

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
