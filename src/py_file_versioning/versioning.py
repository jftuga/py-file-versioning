"""File versioning system with compression and cleanup capabilities.

This module provides a robust file versioning system that supports:
- Multiple compression formats (gzip, bz2, xz)
- Configurable timestamp formats (UTC or local time)
- Automatic version cleanup
- Version restoration
"""

from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

from ._internal import (
    _CompressionType,
    _FileOperations,
    _FileVersioningConfig,
    _TimestampSource,
    _TimezoneFormat,
    _VersionError,
    _VersionInfo,
)


class FileVersioningConfig:
    """Configuration for the file versioning system.

    Args:
        delimiter: String used to separate filename parts in version files. Defaults to "--".
        use_utc: Whether to use UTC timestamps. Defaults to False (local time).
        versions_path: Directory where versions are stored. Defaults to "versions".
        compression: Compression type to use. Options: "none", "gz", "bz2", "xz". Defaults to "none".
        max_versions: Maximum number of versions to keep. None means unlimited. Defaults to None.
        use_modified_time: Use file's modified time instead of current time. Defaults to True.

    Raises:
        ValueError: If any configuration values are invalid.

    Note:
        Version filenames follow the pattern: 'filename{delimiter}YYYYMMDD.HHMMSS_NNN{delimiter}TZ_SRC[.ext]'
        where:
            - TZ is the timezone format ('utc' or 'loc')
            - SRC is the timestamp source ('mod' for modified time, 'sto' for stored time)
            - NNN is a three-digit sequence number
            - .ext is an optional compression extension
    """

    def __init__(
        self,
        delimiter: str = "--",
        use_utc: bool = False,
        versions_path: str = "versions",
        compression: str = "none",
        max_versions: Optional[int] = None,
        use_modified_time: bool = True,
    ):
        """Initialize the configuration with the specified options."""
        try:
            self._config = _FileVersioningConfig(
                delimiter=delimiter,
                timezone_format=_TimezoneFormat.UTC if use_utc else _TimezoneFormat.LOCAL,
                versions_path=versions_path,
                compression=_CompressionType(compression),
                max_versions=max_versions,
                timestamp_format=_TimestampSource.MODIFIED if use_modified_time else _TimestampSource.STORED,
            )
        except ValueError as e:
            raise ValueError(f"Invalid configuration: {str(e)}")

    def __str__(self) -> str:
        """Return a string representation of the configuration.

        Returns:
            str: Formatted string showing all configuration values.
        """
        return (
            f"FileVersioningConfig(\n"
            f"    delimiter: '{self._config.delimiter}'\n"
            f"    timezone: {'UTC' if self._config.timezone_format == _TimezoneFormat.UTC else 'local'}\n"
            f"    versions_path: '{self._config.versions_path}'\n"
            f"    compression: '{self._config.compression.value}'\n"
            f"    max_versions: {self._config.max_versions if self._config.max_versions is not None else 'unlimited'}\n"
            f"    timestamp_source: "
            f"{'modified time' if self._config.timestamp_format == _TimestampSource.MODIFIED else 'stored time'}\n"
            f")"
        )

    def __repr__(self) -> str:
        """Return a detailed string representation of the configuration.

        Returns:
            str: A string representation that can be used to recreate the object.
        """
        return (
            f"{self.__class__.__name__}("
            f"delimiter='{self._config.delimiter}', "
            f"use_utc={self._config.timezone_format == _TimezoneFormat.UTC}, "
            f"versions_path='{self._config.versions_path}', "
            f"compression='{self._config.compression.value}', "
            f"max_versions={self._config.max_versions}, "
            f"use_modified_time={self._config.timestamp_format == _TimestampSource.MODIFIED}"
            f")"
        )


class FileVersioning:
    """A system for managing file versions with compression and cleanup capabilities.

    Creates and manages versioned copies of files with optional compression and automatic
    cleanup of old versions. Each version includes a timestamp and sequence number.

    Args:
        config: Optional configuration object. If None, default settings are used.
    """

    MAX_SEQUENCE = 999
    LIB_NAME = ""
    LIB_VERSION = ""
    LIB_URL = ""

    def __init__(self, config: Optional[FileVersioningConfig] = None):
        """Initialize the versioning system with the given configuration."""
        self.config = config._config if config else _FileVersioningConfig()
        self.versions_path = Path(self.config.versions_path).resolve()
        self.versions_path.mkdir(parents=True, exist_ok=True)

    def create_version(self, file_path: Union[str, Path]) -> Tuple[str, int, str]:
        """Create a new version of the specified file.

        Args:
            file_path: Path to the file to version.

        Returns:
            tuple: A tuple containing:
                - str: Path to the created version file
                - int: Number of old versions removed during cleanup
                - str: Error message from cleanup process, if any

        Raises:
            FileNotFoundError: If the source file doesn't exist.
            OSError: If version creation fails.
        """
        source_path = Path(file_path).resolve()
        if not source_path.exists():
            raise FileNotFoundError(f"Source file {file_path} does not exist")

        try:
            timestamp = _FileOperations.get_timestamp(source_path, self.config.timestamp_format, self.config.timezone_format)
            version_path = self._get_version_path(source_path, timestamp)

            _FileOperations.compress_file(source_path, version_path, self.config.compression)

            removed_count, error_msg = self._cleanup_old_versions(source_path)
            if removed_count < 0:
                removed_count = 0
            return str(version_path), removed_count, error_msg

        except _VersionError as e:
            raise OSError(str(e))
        except Exception as e:
            raise OSError(f"Failed to create version: {str(e)}")

    def restore_version(self, version_path: Union[str, Path], target_path: Union[str, Path]) -> None:
        """Restore a specific version to the target path.

        Args:
            version_path: Path to the version to restore.
            target_path: Path to the file where to restore the version.

        Raises:
            FileNotFoundError: If the version file doesn't exist.
            OSError: If restoration fails or if target_path is a directory.
        """
        version_path = Path(version_path).resolve()
        target_path = Path(target_path).resolve()

        if not version_path.exists():
            raise FileNotFoundError(f"Version file {version_path} does not exist")

        if target_path.is_dir():
            raise OSError(f"Target path {target_path} must be a file path, not a directory")

        # Create parent directories if they don't exist
        target_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            compression = _CompressionType.from_extension(version_path)
            _FileOperations.decompress_file(version_path, target_path, compression)
        except Exception as e:
            raise OSError(f"Failed to restore version: {str(e)}")

    def list_versions(self, file_path: Union[str, Path]) -> List[Dict[str, Union[str, int]]]:
        """List all versions of a file.

        Args:
            file_path: Path to the original file.

        Returns:
            List of dictionaries containing version information:
                - path: Path to the version file
                - timestamp: Creation time of the version (ISO format)
                - size: Size in bytes
                - sequence: Version sequence number
                - timezone_fmt: Timezone format used (utc/loc)
                - timestamp_src: Timestamp source used (mod/sto)
        """
        file_path = Path(file_path)
        versions = self._get_versions(file_path)

        return [
            {
                "path": str(version.path),
                "timestamp": version.timestamp.isoformat(),
                "size": version.size,
                "sequence": version.sequence,
                "timezone_fmt": version.timezone_fmt,
                "timestamp_src": version.timestamp_src,
            }
            for version in [_VersionInfo(v, self.config) for v in versions]
        ]

    def remove_version(self, version_path: Union[str, Path]) -> None:
        """Remove a specific version file.

        Args:
            version_path: Path to the version to remove.

        Raises:
            FileNotFoundError: If the version file doesn't exist.
            OSError: If the file is not a valid version file or removal fails.
        """
        version_path = Path(version_path).resolve()
        if not version_path.exists():
            raise FileNotFoundError(f"Version file {version_path} does not exist")

        try:
            version_path.relative_to(self.versions_path)
        except ValueError:
            raise OSError(f"File {version_path} is not in the versions directory")

        try:
            info = _VersionInfo(version_path, self.config)
            if info.sequence == 0:
                raise _VersionError("Invalid version file")
            version_path.unlink()
        except _VersionError as e:
            raise OSError(str(e))
        except Exception as e:
            raise OSError(f"Failed to remove version: {str(e)}")

    def _get_version_name(self, source_path: Path, timestamp: str) -> str:
        """Generate a version filename.

        Args:
            source_path: Original file path.
            timestamp: Timestamp string.

        Returns:
            Generated version filename.

        Raises:
            RuntimeError: If maximum sequence number is exceeded.
        """
        base = source_path.stem
        ext = source_path.suffix

        sequence = self._get_next_sequence(timestamp, base)
        if sequence > self.MAX_SEQUENCE:
            raise RuntimeError(f"Maximum sequence number ({self.MAX_SEQUENCE}) exceeded")

        version_spec = f"{self.config.timezone_format.value[:3]}_{self.config.timestamp_format.value[:3]}"
        return f"{base}{self.config.delimiter}{timestamp}_{sequence:03d}{self.config.delimiter}{version_spec}{ext}"

    def _get_version_path(self, source_path: Path, timestamp: str) -> Path:
        """Generate a unique version path for the given source file.

        Args:
            source_path: Original file path.
            timestamp: Timestamp string.

        Returns:
            Path object for the new version file.
        """
        version_name = self._get_version_name(source_path, timestamp)

        if self.config.compression != _CompressionType.NONE:
            version_name += f".{self.config.compression.value}"

        return self.versions_path / version_name

    def _get_next_sequence(self, timestamp: str, base_name: str) -> int:
        """Get the next available sequence number for the given timestamp.

        Args:
            timestamp: Timestamp string.
            base_name: Original filename without extension.

        Returns:
            Next available sequence number.
        """
        pattern = f"{base_name}{self.config.delimiter}{timestamp}_*"
        existing = list(self.versions_path.glob(pattern))

        if not existing:
            return 1

        sequences = []
        for path in existing:
            info = _VersionInfo(path, self.config)
            if info.sequence > 0:
                sequences.append(info.sequence)

        return max(sequences, default=0) + 1

    def _get_versions(self, file_path: Path) -> List[Path]:
        """Get all versions of a file sorted by timestamp and sequence.

        Args:
            file_path: Original file path.

        Returns:
            List of Path objects for version files, sorted newest to oldest.
        """
        base = file_path.stem
        pattern = f"{base}{self.config.delimiter}*"
        versions = list(self.versions_path.glob(pattern))

        return sorted(versions, key=lambda p: (_VersionInfo(p, self.config).timestamp, _VersionInfo(p, self.config).sequence), reverse=True)

    def _cleanup_old_versions(self, source_path: Path) -> Tuple[int, str]:
        """Removes older versions if the maximum count is exceeded.

        Analyzes timezone and source types across versions and enforces consistency.
        All versions must have the same timezone and source type.

        Args:
            source_path: Path to the source file.

        Returns:
            tuple: (number of files removed, error message)
                - Negative count if max_versions not set
                - Empty error message if successful
        """
        if not self.config.max_versions:
            return -1, ""

        versions = self._get_versions(source_path)
        all_timezone = defaultdict(int)
        all_timesource = defaultdict(int)

        try:
            for version in versions:
                info = _VersionInfo(version, self.config)
                all_timezone[info.timezone_fmt] += 1
                all_timesource[info.timestamp_src] += 1
        except _VersionError as e:
            return 0, f"Error analyzing versions: {str(e)}"

        if len(all_timezone) > 1:
            tz_types = ", ".join(all_timezone.keys())
            return 0, f"Multiple timezone types not allowed: {tz_types}"

        if len(all_timesource) > 1:
            src_types = ", ".join(all_timesource.keys())
            return 0, f"Multiple source types not allowed: {src_types}"

        files_removed = 0
        while len(versions) > self.config.max_versions:
            try:
                versions.pop().unlink()
                files_removed += 1
            except FileNotFoundError:
                pass  # Ignore if file was already deleted

        return files_removed, ""
