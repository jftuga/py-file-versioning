"""Tests for internal implementation details."""

import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import Generator

import pytest

from py_file_versioning._internal import (
    _CompressionType,
    _FileMetadata,
    _FileOperations,
    _FileVersioningConfig,
    _TimestampSource,
    _TimezoneFormat,
    _VersionError,
    _VersionInfo,
    _VersionSpec,
)


@pytest.fixture
def temp_dir(tmp_path: Path) -> Generator[Path, None, None]:
    """Creates a temporary directory for testing."""
    cwd = os.getcwd()
    os.chdir(tmp_path)
    yield tmp_path
    os.chdir(cwd)


@pytest.fixture
def sample_file(temp_dir: Path) -> Generator[Path, None, None]:
    """Creates a sample file for testing."""
    file_path = temp_dir / "test.txt"
    file_path.write_text("Test content")
    yield file_path
    if file_path.exists():
        file_path.unlink()


class TestCompressionType:
    """Tests for _CompressionType enum."""

    @pytest.mark.parametrize(
        "path_str, expected",
        [
            ("test.txt", _CompressionType.NONE),
            ("test.txt.gz", _CompressionType.GZIP),
            ("test.txt.bz2", _CompressionType.BZ2),
            ("test.txt.xz", _CompressionType.XZ),
            ("test.gz.txt", _CompressionType.NONE),
            ("test", _CompressionType.NONE),
        ],
    )
    def test_from_extension(self, path_str: str, expected: _CompressionType) -> None:
        """Tests compression type detection from file extensions."""
        path = Path(path_str)
        assert _CompressionType.from_extension(path) == expected


class TestTimestampSource:
    """Tests for _TimestampSource enum."""

    def test_values(self) -> None:
        """Tests enum values."""
        assert _TimestampSource.MODIFIED.value == "mod"
        assert _TimestampSource.STORED.value == "sto"


class TestTimezoneFormat:
    """Tests for _TimezoneFormat enum."""

    def test_values(self) -> None:
        """Tests enum values."""
        assert _TimezoneFormat.UTC.value == "utc"
        assert _TimezoneFormat.LOCAL.value == "loc"


class TestVersionSpec:
    """Tests for _VersionSpec class."""

    def test_str_representation(self) -> None:
        """Tests string representation of version spec."""
        spec = _VersionSpec(_TimezoneFormat.UTC, _TimestampSource.MODIFIED)
        assert str(spec) == "utc_mod"

        spec = _VersionSpec(_TimezoneFormat.LOCAL, _TimestampSource.STORED)
        assert str(spec) == "loc_sto"

    def test_from_string_valid(self) -> None:
        """Tests parsing valid version specs from strings."""
        spec = _VersionSpec.from_string("utc_mod")
        assert spec.timezone_fmt == _TimezoneFormat.UTC
        assert spec.timestamp_src == _TimestampSource.MODIFIED

        spec = _VersionSpec.from_string("loc_sto")
        assert spec.timezone_fmt == _TimezoneFormat.LOCAL
        assert spec.timestamp_src == _TimestampSource.STORED

    @pytest.mark.parametrize(
        "invalid_spec",
        [
            "invalid",  # No underscore
            "abc_def",  # Invalid timezone and source
            "utc_invalid",  # Invalid source
            "invalid_mod",  # Invalid timezone
            "ut_mod",  # Too short timezone
            "utc_mo",  # Too short source
            "utcc_modd",  # Too long
            "_",  # Empty parts
            "utc_",  # Missing source
            "_mod",  # Missing timezone
        ],
    )
    def test_from_string_invalid(self, invalid_spec: str) -> None:
        """Tests parsing invalid version specs."""
        with pytest.raises(_VersionError):
            _VersionSpec.from_string(invalid_spec)


class TestVersionInfo:
    """Tests for _VersionInfo class."""

    @pytest.fixture
    def config(self) -> _FileVersioningConfig:
        """Creates a sample configuration."""
        return _FileVersioningConfig(
            delimiter="--",
            timezone_format=_TimezoneFormat.UTC,
            versions_path="versions",
            compression=_CompressionType.NONE,
        )

    @pytest.fixture
    def version_file(self, temp_dir: Path, config: _FileVersioningConfig) -> Path:
        """Creates a sample version file."""
        file_path = temp_dir / "test--20240207.123456_001--utc_mod.txt"
        file_path.write_text("Test content")
        return file_path

    def test_initialization(self, version_file: Path, config: _FileVersioningConfig) -> None:
        """Tests version info initialization."""
        info = _VersionInfo(version_file, config)
        assert info.filename == version_file.name
        assert info.original_name == "test"
        assert isinstance(info.timestamp, datetime)
        assert info.sequence == 1
        assert info.size == len("Test content")
        assert info.compression == _CompressionType.NONE
        assert isinstance(info.version_spec, _VersionSpec)
        assert info.timezone_fmt == "utc"
        assert info.timestamp_src == "mod"

    def test_invalid_filename(self, temp_dir: Path, config: _FileVersioningConfig) -> None:
        """Tests handling of invalid filenames."""
        invalid_file = temp_dir / "invalid_filename.txt"
        invalid_file.write_text("content")

        with pytest.raises(_VersionError):
            _VersionInfo(invalid_file, config)


class TestFileMetadata:
    """Tests for _FileMetadata class."""

    def test_preserve_metadata(self, sample_file: Path, temp_dir: Path) -> None:
        """Tests metadata preservation."""
        dest_file = temp_dir / "dest.txt"
        shutil.copy2(sample_file, dest_file)

        source_stat = sample_file.stat()
        _FileMetadata.preserve_metadata(sample_file, dest_file)
        dest_stat = dest_file.stat()

        assert dest_stat.st_mode == source_stat.st_mode
        assert dest_stat.st_mtime == source_stat.st_mtime
        assert dest_stat.st_atime == source_stat.st_atime


class TestFileVersioningConfig:
    """Tests for _FileVersioningConfig class."""

    def test_default_configuration(self) -> None:
        """Tests default configuration values."""
        config = _FileVersioningConfig()
        assert config.delimiter == "--"
        assert config.timezone_format == _TimezoneFormat.LOCAL
        assert config.versions_path == "versions"
        assert config.compression == _CompressionType.NONE
        assert config.max_versions is None
        assert config.timestamp_format == _TimestampSource.MODIFIED

    def test_invalid_config(self) -> None:
        """Tests validation of invalid configurations."""
        with pytest.raises(ValueError):
            _FileVersioningConfig(max_versions=0)

        with pytest.raises(ValueError):
            _FileVersioningConfig(max_versions=-1)

        with pytest.raises(ValueError):
            _FileVersioningConfig(delimiter="")


class TestFileOperations:
    """Tests for _FileOperations class."""

    @pytest.mark.parametrize("compression", list(_CompressionType))
    def test_compression_cycle(self, compression: _CompressionType, sample_file: Path, temp_dir: Path) -> None:
        """Tests compression and decompression cycle for all compression types."""
        # Skip if NONE compression
        if compression == _CompressionType.NONE:
            return

        # Compress
        compressed_path = temp_dir / f"compressed{sample_file.suffix}.{compression.value}"
        _FileOperations.compress_file(sample_file, compressed_path, compression)
        assert compressed_path.exists()
        assert compressed_path.stat().st_size > 0

        # Decompress
        decompressed_path = temp_dir / f"decompressed{sample_file.suffix}"
        _FileOperations.decompress_file(compressed_path, decompressed_path, compression)
        assert decompressed_path.exists()
        assert decompressed_path.read_text() == sample_file.read_text()

    @pytest.mark.parametrize(
        "source,tz_format",
        [
            (_TimestampSource.MODIFIED, _TimezoneFormat.UTC),
            (_TimestampSource.MODIFIED, _TimezoneFormat.LOCAL),
            (_TimestampSource.STORED, _TimezoneFormat.UTC),
            (_TimestampSource.STORED, _TimezoneFormat.LOCAL),
        ],
    )
    def test_get_timestamp(
        self,
        source: _TimestampSource,
        tz_format: _TimezoneFormat,
        sample_file: Path,
    ) -> None:
        """Tests timestamp generation with different configurations."""
        timestamp = _FileOperations.get_timestamp(sample_file, source, tz_format)
        assert len(timestamp) == 15  # YYYYMMDD.HHMMSS
        assert "." in timestamp
        assert timestamp.replace(".", "").isdigit()

    def test_parse_version_filename(self) -> None:
        """Tests version filename parsing."""
        # Test valid filename
        base, timestamp, sequence = _FileOperations.parse_version_filename("test--20240207.123456_001--utc_mod.txt", "--")
        assert base == "test"
        assert timestamp == "20240207.123456"
        assert sequence == 1

        # Test invalid filename
        base, timestamp, sequence = _FileOperations.parse_version_filename("invalid_filename.txt", "--")
        assert base == "invalid_filename.txt"
        assert timestamp == ""
        assert sequence == 0
