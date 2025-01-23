"""File versioning package with compression support."""

from .file_versioning import (
    CompressionType,
    FileVersioning,
    FileVersioningConfig,
    TimestampSource,
    TimezoneFormat,
    VersionError,
    VersionInfo,
)

__version__ = "0.9.0"
__all__ = [
    "FileVersioning",
    "FileVersioningConfig",
    "CompressionType",
    "TimestampSource",
    "TimezoneFormat",
    "VersionError",
    "VersionInfo",
]

FileVersioning.LIB_NAME = "py-file-versioning"
FileVersioning.LIB_URL = "https://github.com/jftuga/py-file-versioning"
FileVersioning.LIB_VERSION = __version__
