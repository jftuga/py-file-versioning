# py-file-versioning

A flexible file versioning system with compression support, written in Python.

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

Restore a specific version:
```bash
pyfileversioning restore versions/myfile--20240120.123456_001.txt.gz --target restored_file.txt
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
$ pyfileversioning create config.ini -d backups  # or --versions-dir backups
Created version: backups/config--20240120.143022_001.ini

# Update the file content
$ echo "database_port=5432" >> config.ini

# Create compressed version
$ pyfileversioning create config.ini -d backups -c gz  # Using short options
Created version: backups/config--20240120.143156_001.ini.gz

# List all versions
$ pyfileversioning list config.ini -d backups
Versions for config.ini:
------------------------------------------------------------
config--20240120.143156_001.ini.gz           285 bytes  2024-01-20 14:31:56
config--20240120.143022_001.ini              187 bytes  2024-01-20 14:30:22

# Add more content and create another version
$ echo "database_name=myapp" >> config.ini

$ pyfileversioning create config.ini --versions-dir backups --compression gz
Created version: backups/config--20240120.143312_001.ini.gz

# View all versions with size and timestamp
$ pyfileversioning list config.ini --versions-dir backups
Versions for config.ini:
------------------------------------------------------------
config--20240120.143312_001.ini.gz           324 bytes  2024-01-20 14:33:12
config--20240120.143156_001.ini.gz           285 bytes  2024-01-20 14:31:56
config--20240120.143022_001.ini              187 bytes  2024-01-20 14:30:22

# Restore the first version
$ pyfileversioning restore backups/config--20240120.143022_001.ini --target config.ini.restored
Restored backups/config--20240120.143022_001.ini to config.ini.restored

# Verify the restored content
$ cat config.ini.restored
database_host=localhost

# Clean up old versions (only keep the last 2)
$ pyfileversioning create config.ini -d backups -c gz -m 2  # Using short options
Created version: backups/config--20240120.143428_001.ini.gz

# Check that only 2 versions remain
$ pyfileversioning list config.ini --versions-dir backups
Versions for config.ini:
------------------------------------------------------------
config--20240120.143428_001.ini.gz           324 bytes  2024-01-20 14:34:28
config--20240120.143312_001.ini.gz           324 bytes  2024-01-20 14:33:12
```


### Python API Usage

See [create-demo.py](create-demo.py) for a more detailed example.

```python
import os
from py_file_versioning import FileVersioning, FileVersioningConfig, CompressionType

# Create a test file
TEST_FILE="test_file.txt"
if not os.path.exists(TEST_FILE):
    with open(TEST_FILE, mode="w") as fp:
        fp.write("this is a test file\n")

# Basic usage
versioning = FileVersioning()
version_path = versioning.create_version(TEST_FILE)

# Advanced configuration
config = FileVersioningConfig(
    versioned_path="backups",
    compression=CompressionType.GZIP,
    max_count=5  # Keep only last 5 versions
)
versioning = FileVersioning(config)
version_path = versioning.create_version(TEST_FILE)
```

## Configuration Options

### FileVersioningConfig Parameters

| Parameter | Type | Default    | Description |
|-----------|------|------------|-------------|
| delimiter | str | "--"       | Separator between filename and version information |
| timezone_format | TimezoneFormat | LOCAL      | Timestamp timezone (LOCAL or UTC) |
| versioned_path | str | "versions" | Directory to store versions |
| compression | CompressionType | NONE       | Compression type (NONE, GZIP, BZ2, XZ) |
| max_count | Optional[int] | None       | Maximum number of versions to keep |
| timestamp_format | TimestampSource | MODIFIED   | Source for timestamps (MODIFIED or NOW) |

### Command Line Options

```
usage: pyfileversioning [-h] [-V] [-t TARGET] [-d VERSIONS_DIR]
                [-c {none,gz,bz2,xz}] [-m MAX_VERSIONS]
                [--timestamp-source {modified,now}]
                {create,restore,list,remove} file
```

Options:
* `-V, --version`: Show version information
* `-t, --target`: Target path for restore
* `-d, --versions-dir`: Directory to store versions (default: versions)
* `-c, --compression`: Compression type to use (choices: none, gz, bz2, xz)
* `-m, --max-versions`: Maximum number of versions to keep
* `--timestamp-source`: Source for timestamps (choices: modified, now)

## Examples

### Maintaining Multiple Versions

```python
from py_file_versioning import FileVersioning, FileVersioningConfig

config = FileVersioningConfig(
    versioned_path="versions",
    max_count=5  # Keep only last 5 versions
)
versioning = FileVersioning(config)

# Create versions
for i in range(10):
    with open("test.txt", "w") as f:
        f.write(f"Version {i+1}\n")
    versioning.create_version("test.txt")
```

### Using Different Compression Types

```python
from py_file_versioning import FileVersioning, FileVersioningConfig, CompressionType

# Create versions with different compression types
for compression in [CompressionType.NONE, CompressionType.GZIP, CompressionType.BZ2, CompressionType.XZ]:
    config = FileVersioningConfig(
        versioned_path="versions",
        compression=compression
    )
    versioning = FileVersioning(config)
    version_path = versioning.create_version("myfile.txt")
```

### Version File Naming

Version files follow this naming pattern:
```
{original_name}{delimiter}{timestamp}_{sequence}{extension}[.compression_ext]
```

Example:
```
myfile--20240120.123456_001.txt.gz
```

Where:
- `myfile` is the original filename
- `--` is the delimiter
- `20240120.123456` is the timestamp (YYYYMMDD.HHMMSS)
- `001` is the sequence number
- `.txt` is the original extension
- `.gz` is the compression extension (if compression is used)

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
