"""File versioning system with compression support."""

from .versioning import FileVersioning, FileVersioningConfig

__version__ = "0.10.0"
__all__ = ["FileVersioning", "FileVersioningConfig"]

FileVersioning.LIB_NAME = "py-file-versioning"
FileVersioning.LIB_URL = "https://github.com/jftuga/py-file-versioning"
FileVersioning.LIB_VERSION = __version__
