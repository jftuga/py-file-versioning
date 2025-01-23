import bz2
import gzip
import lzma
import shutil
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import List, Optional, Tuple


class VersionError(Exception):
    """Custom exception for versioning errors."""

    pass


class CompressionType(Enum):
    NONE = "none"
    GZIP = "gzip"
    BZ2 = "bz2"
    XZ = "xz"


class TimestampSource(Enum):
    MODIFIED = "modified"
    NOW = "now"


class TimezoneFormat(Enum):
    UTC = "utc"
    LOCAL = "local"


@dataclass
class FileVersioningConfig:
    delimiter: str = "--"
    timezone_format: TimezoneFormat = TimezoneFormat.LOCAL
    versioned_path: str = "versions"
    compression: CompressionType = CompressionType.NONE
    max_count: Optional[int] = None
    timestamp_format: TimestampSource = TimestampSource.MODIFIED


@dataclass
class VersionInfo:
    """Information about a specific version of a file.

    Attributes:
        path (Path): Path to the version file
        config (FileVersioningConfig): Configuration settings used for versioning
        filename (str): Name of the version file
        original_name (str): Original filename without version information
        timestamp (datetime): Creation timestamp of the version
        sequence (int): Sequence number of the version
        size (int): Size of the version file in bytes
        compression (CompressionType): Compression type used for this version
    """

    path: Path
    config: "FileVersioningConfig"
    filename: str = field(init=False)
    original_name: str = field(init=False)
    timestamp: datetime = field(init=False)
    sequence: int = field(init=False)
    size: int = field(init=False)
    compression: CompressionType = field(init=False)

    def __post_init__(self) -> None:
        """Initialize calculated fields after instance creation.

        This method is automatically called after the dataclass is instantiated.
        It calculates and sets various attributes based on the version file's path
        and name.

        The following attributes are set:
            filename: Extracted from the path
            size: File size in bytes
            compression: Determined from file extension
            original_name: Parsed from the version filename
            sequence: Extracted sequence number
            timestamp: Parsed from the version filename
        """
        self.filename = self.path.name
        self.size = self.path.stat().st_size
        self.compression = self._determine_compression()
        self.original_name, timestamp_str, self.sequence = self._parse_filename()
        self.timestamp = datetime.strptime(timestamp_str, "%Y%m%d.%H%M%S")

    def _determine_compression(self) -> CompressionType:
        """Determine the compression type from the version file's extension.

        This method examines the file extension to determine what compression
        method, if any, was used for this version.

        Returns:
            CompressionType: The compression type used for this version.
            Returns CompressionType.NONE if no compression is detected.
        """
        suffixes = self.path.suffixes
        if not suffixes:
            return CompressionType.NONE
        ext = suffixes[-1].lower()
        compression_map = {
            ".gz": CompressionType.GZIP,
            ".bz2": CompressionType.BZ2,
            ".xz": CompressionType.XZ,
        }
        return compression_map.get(ext, CompressionType.NONE)

    def _parse_filename(self) -> Tuple[str, str, int]:
        """Parse the version filename into its components.

        This method breaks down the version filename into its constituent parts
        using the configured delimiter.

        Returns:
            tuple: A tuple containing:
                - str: The original base filename
                - str: The timestamp string (YYYYMMDD.HHMMSS format)
                - int: The sequence number

        Raises:
                ValueError: If the filename doesn't match the expected format
        """
        parts = self.filename.split(self.config.delimiter)
        if len(parts) != 2:
            raise ValueError("Invalid version filename format")

        base_name = parts[0]
        version_info = parts[1]

        try:
            # Try to extract timestamp and verify it has correct length
            if len(version_info) < 19:  # Minimum length needed for timestamp and sequence
                raise ValueError("Invalid version filename format")

            timestamp = version_info[:15]  # YYYYMMDD.HHMMSS
            # Verify timestamp format
            if not (len(timestamp) == 15 and "." in timestamp and timestamp.replace(".", "").isdigit()):
                raise ValueError("Invalid version filename format")

            # Verify underscore separator
            if version_info[15] != "_":
                raise ValueError("Invalid version filename format")

            # Extract sequence after underscore
            sequence_str = version_info[16:19]
            if not sequence_str.isdigit():
                raise ValueError("Invalid version filename format")

            sequence = int(sequence_str)
            return base_name, timestamp, sequence

        except (IndexError, ValueError) as e:
            if str(e) == "Invalid version filename format":
                raise
            raise ValueError("Invalid version filename format") from e


class FileVersioning:
    """A class for managing file versioning with configurable timestamps, compression, and cleanup.

    This class provides functionality to create, restore, and manage versioned copies of files
    with support for different compression methods (gzip, bz2, xz), timestamp formats,
    and automatic cleanup of old versions. Each version is stored with a timestamp
    and sequence number to maintain unique identifiers.

    Attributes:
        MAX_SEQUENCE (int): Maximum allowed sequence number for versions (999).
        LIB_NAME (str): Name of the library.
        LIB_VERSION (str): Version of the library.
        LIB_URL (str): URL to the library's repository.
    """

    MAX_SEQUENCE = 999
    LIB_NAME = "pyfileversioning"
    LIB_VERSION = ""
    LIB_URL = "https://github.com/jftuga/py_file_versioning"

    def __init__(self, config: FileVersioningConfig = None):
        """Initialize the FileVersioning instance with the given configuration.

        Args:
            config: Configuration object for versioning settings. If None, default settings will be used.
        """
        self.config = config or FileVersioningConfig()

        # Convert versioned_path to absolute path and create if needed
        self.versioned_path = Path(self.config.versioned_path).resolve()
        self.versioned_path.mkdir(parents=True, exist_ok=True)

    def _parse_version_filename(self, filename: str) -> Tuple[str, str, int]:
        """Parse a version filename into its components.

        Args:
            filename: The filename to parse.

        Returns:
            A tuple containing:
                - base_name (str): The original filename without version information
                - timestamp (str): The timestamp portion of the filename
                - sequence (int): The sequence number of the version

        Note:
            Expected filename format: {base_name}{delimiter}{YYYYMMDD.HHMMSS}_{sequence}
        """
        try:
            # Split on delimiter
            base_name = filename.split(self.config.delimiter)[0]
            # Extract timestamp and sequence
            rest = filename[len(base_name) + len(self.config.delimiter) :]  # noqa
            timestamp = rest[:15]  # YYYYMMDD.HHMMSS
            if "_" in rest:
                sequence = int(rest[16:19])  # Extract sequence after underscore
            else:
                sequence = 0
            return base_name, timestamp, sequence
        except (IndexError, ValueError):
            return base_name, "", 0

    def _get_next_sequence(self, timestamp: str, base_name: str) -> int:
        """Get the next available sequence number for a given timestamp.

        Args:
            timestamp: The timestamp string in YYYYMMDD.HHMMSS format.
            base_name: The base name of the file.

        Returns:
            The next available sequence number.

        Raises:
            VersionError: If the maximum sequence number is exceeded.
        """
        pattern = f"{base_name}{self.config.delimiter}{timestamp}_*"
        existing = list(self.versioned_path.glob(pattern))

        if not existing:
            return 1

        sequences = []
        for path in existing:
            _, _, seq = self._parse_version_filename(path.name)
            sequences.append(seq)

        next_seq = max(sequences, default=0) + 1
        if next_seq > self.MAX_SEQUENCE:
            raise VersionError(f"Maximum sequence number ({self.MAX_SEQUENCE}) exceeded for timestamp {timestamp}")

        return next_seq

    def _get_timestamp(self, file_path: Path) -> str:
        """Generate a timestamp string based on configuration settings.

        Args:
            file_path: Path to the file for which to generate the timestamp.

        Returns:
            A formatted timestamp string in YYYYMMDD.HHMMSS format.
        """
        if self.config.timestamp_format == TimestampSource.MODIFIED:
            # Get timestamp based on file modification time
            timestamp = datetime.fromtimestamp(file_path.stat().st_mtime)
        else:
            # Get current timestamp
            timestamp = datetime.now()

        # Handle timezone conversion if needed
        if self.config.timezone_format == TimezoneFormat.UTC:
            if timestamp.tzinfo is None:
                # Convert naive datetime to UTC
                timestamp = timestamp.astimezone(timezone.utc)
            else:
                # Convert aware datetime to UTC
                timestamp = timestamp.astimezone(timezone.utc)
        else:
            # For local time, we use the naive datetime as is
            pass

        return timestamp.strftime("%Y%m%d.%H%M%S")

    def _get_versioned_filename(self, original_path: Path, timestamp: str) -> Path:
        """Generate a unique versioned filename with appropriate extensions.

        Args:
            original_path: The original file path.
            timestamp: The timestamp string to use in the versioned filename.

        Returns:
            A Path object representing the new versioned filename.
        """
        base = original_path.stem
        ext = original_path.suffix

        # Get next sequence number
        sequence = self._get_next_sequence(timestamp, base)
        versioned_name = f"{base}{self.config.delimiter}{timestamp}_{sequence:03d}{ext}"

        if self.config.compression != CompressionType.NONE:
            compression_ext = {
                CompressionType.GZIP: ".gz",
                CompressionType.BZ2: ".bz2",
                CompressionType.XZ: ".xz",
            }
            versioned_name += compression_ext[self.config.compression]

        return self.versioned_path / versioned_name

    def _compress_file(self, source_path: Path, dest_path: Path) -> None:
        """Compress a file using the configured compression method.

        Args:
            source_path: Path to the source file to compress.
            dest_path: Path where the compressed file should be saved.
        """
        compression_handlers = {
            CompressionType.GZIP: gzip.open,
            CompressionType.BZ2: bz2.open,
            CompressionType.XZ: lzma.open,
        }

        if self.config.compression in compression_handlers:
            with source_path.open("rb") as f_in:
                with compression_handlers[self.config.compression](str(dest_path), "wb") as f_out:
                    shutil.copyfileobj(f_in, f_out)
        else:
            shutil.copy2(str(source_path), str(dest_path))

    def _cleanup_old_versions(self, base_name: Path) -> None:
        """Remove old versions of a file based on max_count configuration.

        Args:
            base_name: Path object representing the original file name.

        Note:
            If max_count is None, no cleanup will be performed.
        """
        if not self.config.max_count:
            return

        while True:
            # Get fresh list of versions, sorted newest to oldest
            versions = self._get_versions(base_name)

            # If we're at or below max_count, we're done
            if len(versions) <= self.config.max_count:
                break

            # Remove oldest version
            oldest = versions[-1]  # Get oldest (last since sorted newest first)
            try:
                oldest.unlink()
            except FileNotFoundError:
                pass  # Ignore if file was already deleted

    def _get_versions(self, file_path: Path) -> List[Path]:
        """Get all versions of a file sorted by timestamp and sequence number.

        Args:
            file_path: Path to the original file.

        Returns:
            A list of Path objects representing all versions of the file,
            sorted newest to oldest.
        """
        base = file_path.stem
        pattern = f"{base}{self.config.delimiter}*"
        versions = list(self.versioned_path.glob(pattern))

        # Sort by timestamp and sequence number (newest first)
        return sorted(versions, key=lambda p: self._parse_version_filename(p.name)[1:3], reverse=True)

    def create_version(self, file_path: str) -> str:
        """Create a new version of the specified file.

        Args:
            file_path: Absolute or relative path to the source file.

        Returns:
            String representation of the path to the created version.

        Raises:
            FileNotFoundError: If the source file doesn't exist.
            VersionError: If maximum sequence number is exceeded.
        """
        source_path = Path(file_path).resolve()
        if not source_path.exists():
            raise FileNotFoundError(f"Source file {file_path} does not exist")

        timestamp = self._get_timestamp(source_path)
        versioned_path = self._get_versioned_filename(source_path, timestamp)

        self._compress_file(source_path, versioned_path)
        self._cleanup_old_versions(source_path)

        return str(versioned_path)

    def _get_compression_from_path(self, path: Path) -> CompressionType:
        """Determine the compression type from a file's extension.

        Args:
            path: Path object to analyze.

        Returns:
            CompressionType enum value representing the detected compression type.
        """
        suffixes = path.suffixes
        if not suffixes:
            return CompressionType.NONE
        ext = suffixes[-1].lower()
        compression_map = {
            ".gz": CompressionType.GZIP,
            ".bz2": CompressionType.BZ2,
            ".xz": CompressionType.XZ,
        }
        return compression_map.get(ext, CompressionType.NONE)

    def restore_version(self, version_path: str, target_path: str) -> None:
        """Restore a specific version to the target path.

        Args:
            version_path: Path to the version to restore.
            target_path: Path where the version should be restored.

        Raises:
            FileNotFoundError: If the version file doesn't exist.
        """
        version_path = Path(version_path).resolve()
        target_path = Path(target_path).resolve()

        if not version_path.exists():
            raise FileNotFoundError(f"Version file {version_path} does not exist")

        # Create target directory if it doesn't exist
        target_path.parent.mkdir(parents=True, exist_ok=True)

        # Determine compression from file extension
        compression = self._get_compression_from_path(version_path)

        if compression != CompressionType.NONE:
            decompression_handlers = {
                CompressionType.GZIP: gzip.open,
                CompressionType.BZ2: bz2.open,
                CompressionType.XZ: lzma.open,
            }

            with decompression_handlers[compression](str(version_path), "rb") as f_in:
                with target_path.open("wb") as f_out:
                    shutil.copyfileobj(f_in, f_out)
        else:
            shutil.copy2(str(version_path), str(target_path))

    def list_versions(self, file_path: str) -> List[VersionInfo]:
        """List all versions of a file.

        Args:
            file_path: Path to the original file.

        Returns:
            List of VersionInfo objects containing details about each version,
            sorted from newest to oldest.
        """
        file_path = Path(file_path)
        versions = self._get_versions(file_path)
        return [VersionInfo(path=version, config=self.config) for version in versions]

    def remove_version(self, version_path: str) -> None:
        """Remove a specific version file.

        Args:
            version_path: Path to the version to remove.

        Raises:
            FileNotFoundError: If the version file doesn't exist.
            VersionError: If the file is not in the versioned directory or not a valid version file.
        """
        version_path = Path(version_path).resolve()
        if not version_path.exists():
            raise FileNotFoundError(f"Version file {version_path} does not exist")

        # Check if the file is within the versioned directory
        try:
            version_path.relative_to(self.versioned_path)
        except ValueError:
            raise VersionError(f"File {version_path} is not in the versioned directory {self.versioned_path}")

        # Verify the file follows the version naming pattern
        base_name, timestamp, sequence = self._parse_version_filename(version_path.name)
        if not timestamp or sequence == 0:
            raise VersionError(f"File {version_path.name} does not follow the version naming pattern")

        version_path.unlink()
