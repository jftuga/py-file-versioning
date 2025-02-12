"""Internal implementation details for file versioning system.

This module contains internal classes and utilities that should not be
imported directly by users of the file versioning system.

Note:
    All classes and functions in this module are considered internal implementation
    details and may change without notice.
"""

import bz2
import gzip
import lzma
import os
import shutil
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Optional, Tuple


class _CompressionType(Enum):
    """Internal enum for compression types.

    Attributes:
        NONE: No compression.
        GZIP: GNU zip compression.
        BZ2: Bzip2 compression.
        XZ: LZMA compression.
    """

    NONE = "none"
    GZIP = "gz"
    BZ2 = "bz2"
    XZ = "xz"

    @classmethod
    def from_extension(cls, path: Path) -> "_CompressionType":
        """Determines compression type from file extension.

        Args:
            path: Path object to analyze for compression extension.

        Returns:
            CompressionType enum value corresponding to the file extension.
            Returns NONE if no recognized compression extension is found.
        """
        suffixes = path.suffixes
        if not suffixes:
            return cls.NONE
        ext = suffixes[-1].lower()
        compression_map = {
            ".gz": cls.GZIP,
            ".bz2": cls.BZ2,
            ".xz": cls.XZ,
        }
        return compression_map.get(ext, cls.NONE)


class _TimestampSource(Enum):
    """Internal enum for timestamp source selection.

    Attributes:
        MODIFIED: Use file's modification time.
        STORED: Use current time when version is created.
    """

    MODIFIED = "mod"
    STORED = "sto"


class _TimezoneFormat(Enum):
    """Internal enum for timezone format selection.

    Attributes:
        UTC: Use UTC timezone.
        LOCAL: Use local timezone.
    """

    UTC = "utc"
    LOCAL = "loc"


class _VersionError(Exception):
    """Internal exception for versioning errors.

    This exception is raised when version-related operations fail.
    """

    pass


@dataclass
class _VersionSpec:
    """Internal class for version specification components.

    Attributes:
        timezone_fmt: Timezone format to use for timestamps.
        timestamp_src: Source to use for timestamp values.
    """

    timezone_fmt: _TimezoneFormat
    timestamp_src: _TimestampSource

    def __str__(self) -> str:
        """Converts specification to string format used in filenames.

        Returns:
            String representation in the format 'TZ_SRC' where:
                TZ is the first 3 letters of the timezone format
                SRC is the first 3 letters of the timestamp source
        """
        return f"{self.timezone_fmt.value[:3]}_{self.timestamp_src.value[:3]}"

    @classmethod
    def from_string(cls, spec_str: str) -> "_VersionSpec":
        """Parses version specification from filename component.

        Args:
            spec_str: String in format 'TZ_SRC' to parse.

        Returns:
            VersionSpec instance with parsed values.

        Raises:
            _VersionError: If the specification string is invalid.
        """
        try:
            # Check basic string format
            if not spec_str or "_" not in spec_str:
                raise ValueError("Missing underscore separator")

            tz_str, src_str = spec_str.split("_")

            # Validate each component is present
            if not tz_str or not src_str:
                raise ValueError("Empty timezone or source component")

            # Try to create the enums - this will validate the values
            try:
                timezone_fmt = _TimezoneFormat("utc" if tz_str == "utc" else "loc")
                if tz_str not in ["utc", "loc"]:
                    raise ValueError(f"Invalid timezone format: {tz_str}")
            except ValueError as e:
                raise ValueError(f"Invalid timezone format: {tz_str}") from e

            try:
                timestamp_src = _TimestampSource("mod" if src_str == "mod" else "sto")
                if src_str not in ["mod", "sto"]:
                    raise ValueError(f"Invalid timestamp source: {src_str}")
            except ValueError as e:
                raise ValueError(f"Invalid timestamp source: {src_str}") from e

            return cls(
                timezone_fmt=timezone_fmt,
                timestamp_src=timestamp_src,
            )
        except ValueError as e:
            raise _VersionError(f"Invalid version specification format: {spec_str} - {str(e)}") from e


@dataclass
class _VersionInfo:
    """Internal class for storing version information.

    Attributes:
        path: Path to the version file.
        config: Configuration settings for version handling.
        filename: Name of the version file (derived).
        original_name: Original filename without version info (derived).
        timestamp: Creation timestamp of the version (derived).
        sequence: Version sequence number (derived).
        size: File size in bytes (derived).
        compression: Type of compression used (derived).
        version_spec: Version specification details (derived).
    """

    path: Path
    config: "_FileVersioningConfig"
    filename: str = field(init=False)
    original_name: str = field(init=False)
    timestamp: datetime = field(init=False)
    sequence: int = field(init=False)
    size: int = field(init=False)
    compression: _CompressionType = field(init=False)
    version_spec: _VersionSpec = field(init=False)

    def __post_init__(self) -> None:
        """Initializes derived fields after instance creation."""
        self.filename = self.path.name
        self.size = self.path.stat().st_size
        self.compression = _CompressionType.from_extension(self.path)
        self.original_name, timestamp_str, self.sequence, spec_str = self._parse_filename()
        self.timestamp = datetime.strptime(timestamp_str, "%Y%m%d.%H%M%S")
        self.version_spec = _VersionSpec.from_string(spec_str)

    def _parse_filename(self) -> Tuple[str, str, int, str]:
        """Parses version filename into components.

        Returns:
            Tuple containing:
                - Original filename
                - Timestamp string
                - Sequence number
                - Version specification string

        Raises:
            _VersionError: If filename format is invalid.
        """
        try:
            parts = self.filename.split(self.config.delimiter)
            if len(parts) != 3:
                raise _VersionError("Invalid version filename format: wrong number of parts")

            base_name = parts[0]
            version_info = parts[1]
            spec_str = parts[2].split(".")[0]  # Remove any compression extension

            if len(version_info) < 19:
                raise _VersionError("Invalid version info length")

            timestamp = version_info[:15]  # YYYYMMDD.HHMMSS
            if not (len(timestamp) == 15 and "." in timestamp and timestamp.replace(".", "").isdigit()):
                raise _VersionError("Invalid timestamp format")

            sequence_str = version_info[16:19]
            if not sequence_str.isdigit():
                raise _VersionError("Invalid sequence number")

            sequence = int(sequence_str)
            return base_name, timestamp, sequence, spec_str

        except (IndexError, ValueError) as e:
            raise _VersionError("Invalid version filename format") from e

    @property
    def timezone_fmt(self) -> str:
        """Gets timezone format string.

        Returns:
            String representation of the timezone format.
        """
        return self.version_spec.timezone_fmt.value

    @property
    def timestamp_src(self) -> str:
        """Gets timestamp source string.

        Returns:
            String representation of the timestamp source.
        """
        return self.version_spec.timestamp_src.value


class _FileMetadata:
    """Base class for file metadata operations."""

    @staticmethod
    def preserve_metadata(source: Path, dest: Path) -> None:
        """Preserves metadata from source file to destination file.

        Args:
            source: Source file path to copy metadata from.
            dest: Destination file path to copy metadata to.
        """
        source_stat = source.stat()
        os.utime(dest, (source_stat.st_atime, source_stat.st_mtime))
        os.chmod(dest, source_stat.st_mode)


@dataclass
class _FileVersioningConfig:
    """Internal configuration class for file versioning.

    Attributes:
        delimiter: String used to separate filename parts.
        timezone_format: Format to use for timestamps.
        versions_path: Directory where versions are stored.
        compression: Type of compression to use.
        max_versions: Maximum number of versions to keep.
        timestamp_format: Source for timestamp values.
    """

    delimiter: str = "--"
    timezone_format: _TimezoneFormat = _TimezoneFormat.LOCAL
    versions_path: str = "versions"
    compression: _CompressionType = _CompressionType.NONE
    max_versions: Optional[int] = None
    timestamp_format: _TimestampSource = _TimestampSource.MODIFIED

    def __post_init__(self):
        """Validates configuration after initialization.

        Raises:
            ValueError: If configuration values are invalid.
        """
        if self.max_versions is not None and self.max_versions <= 0:
            raise ValueError("max_versions must be positive if specified")
        if not self.delimiter:
            raise ValueError("delimiter cannot be empty")


class _FileOperations(_FileMetadata):
    """Internal utility class for file operations."""

    @classmethod
    def compress_file(cls, source_path: Path, dest_path: Path, compression: _CompressionType) -> None:
        """Compresses a file using the specified compression method.

        Args:
            source_path: Path to the source file to compress.
            dest_path: Path where compressed file will be written.
            compression: Type of compression to use.
        """
        compression_handlers = {
            _CompressionType.GZIP: lambda path: gzip.open(path, "wb", compresslevel=9),
            _CompressionType.BZ2: lambda path: bz2.open(path, "wb", compresslevel=9),
            _CompressionType.XZ: lambda path: lzma.open(path, "wb", preset=9),
        }

        if compression in compression_handlers:
            with source_path.open("rb") as f_in:
                with compression_handlers[compression](str(dest_path)) as f_out:
                    shutil.copyfileobj(f_in, f_out)
        else:
            shutil.copy2(str(source_path), str(dest_path))

        cls.preserve_metadata(source_path, dest_path)

    @classmethod
    def decompress_file(cls, source_path: Path, dest_path: Path, compression: _CompressionType) -> None:
        """Decompresses a file using the specified compression method.

        Args:
            source_path: Path to the compressed source file.
            dest_path: Path where decompressed file will be written.
            compression: Type of compression used in source file.
        """
        if compression != _CompressionType.NONE:
            decompression_handlers = {
                _CompressionType.GZIP: gzip.open,
                _CompressionType.BZ2: bz2.open,
                _CompressionType.XZ: lzma.open,
            }

            with decompression_handlers[compression](str(source_path), "rb") as f_in:
                with dest_path.open("wb") as f_out:
                    shutil.copyfileobj(f_in, f_out)
        else:
            shutil.copy2(str(source_path), str(dest_path))

        cls.preserve_metadata(source_path, dest_path)

    @staticmethod
    def get_timestamp(file_path: Path, source: _TimestampSource, tz_format: _TimezoneFormat) -> str:
        """Generates a timestamp string based on configuration.

        Args:
            file_path: Path to file to get timestamp for.
            source: Source to use for timestamp value.
            tz_format: Timezone format to use.

        Returns:
            Formatted timestamp string in "YYYYMMDD.HHMMSS" format.
        """
        if source == _TimestampSource.MODIFIED:
            timestamp = datetime.fromtimestamp(file_path.stat().st_mtime)
        else:
            timestamp = datetime.now()

        if tz_format == _TimezoneFormat.UTC:
            timestamp = timestamp.astimezone(timezone.utc)

        return timestamp.strftime("%Y%m%d.%H%M%S")

    @staticmethod
    def parse_version_filename(filename: str, delimiter: str) -> Tuple[str, str, int]:
        """Parses a version filename into its components.

        Args:
            filename: Version filename to parse.
            delimiter: Delimiter used in version filenames.

        Returns:
            Tuple containing:
                - Original filename
                - Timestamp string
                - Sequence number

        Note:
            Returns default values ("", "", 0) if parsing fails.
        """
        try:
            parts = filename.split(delimiter)
            if len(parts) < 2:
                return parts[0] if parts else "", "", 0

            base_name = parts[0]
            version_info = parts[1]
            timestamp = version_info[:15]  # YYYYMMDD.HHMMSS
            sequence = int(version_info[16:19]) if len(version_info) >= 19 else 0

            return base_name, timestamp, sequence
        except (IndexError, ValueError):
            return base_name if parts else "", "", 0
