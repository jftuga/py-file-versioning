import os
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import pytest

from py_file_versioning import (
    CompressionType,
    FileVersioning,
    FileVersioningConfig,
    TimestampSource,
    TimezoneFormat,
    VersionError,
    VersionInfo,
)


@pytest.fixture
def temp_dir():
    """Create a temporary directory for testing."""
    temp_dir = tempfile.mkdtemp()
    yield Path(temp_dir)
    shutil.rmtree(temp_dir)


@pytest.fixture
def sample_file(temp_dir):
    """Create a sample file for testing."""
    file_path = temp_dir / "test_file.txt"
    with file_path.open("w") as f:
        f.write("Test content")
    yield file_path


@pytest.fixture
def unicode_file(temp_dir):
    """Create a sample file with Unicode name for testing."""
    file_path = temp_dir / "????.txt"
    with file_path.open("w") as f:
        f.write("Unicode test content")
    yield file_path


def test_default_config():
    """Test FileVersioning with default configuration."""
    config = FileVersioningConfig()
    # versioning = FileVersioning(config)

    assert config.delimiter == "--"
    assert config.timezone_format == TimezoneFormat.LOCAL
    assert config.versioned_path == "versions"
    assert config.compression == CompressionType.NONE
    assert config.max_count is None
    assert config.timestamp_format == TimestampSource.MODIFIED


def test_sequence_numbers(temp_dir, sample_file):
    """Test sequence number generation in versioned filenames."""
    config = FileVersioningConfig(
        versioned_path=str(temp_dir),
        timestamp_format=TimestampSource.NOW,  # Use NOW to ensure same timestamp
    )
    versioning = FileVersioning(config)

    # Create multiple versions rapidly to get same timestamp
    version_paths = []
    for _ in range(3):
        version_path = versioning.create_version(str(sample_file))
        version_paths.append(Path(version_path))

    # Verify sequence numbers
    for i, path in enumerate(version_paths, start=1):
        assert f"_{i:03d}" in path.name
        assert path.exists()


def test_sequence_parsing(temp_dir, sample_file):
    """Test parsing of versioned filenames."""
    config = FileVersioningConfig(versioned_path=str(temp_dir))
    versioning = FileVersioning(config)

    version_path = versioning.create_version(str(sample_file))
    filename = Path(version_path).name

    base, timestamp, sequence = versioning._parse_version_filename(filename)
    assert base == "test_file"
    assert len(timestamp) == 15  # YYYYMMDD.HHMMSS
    assert sequence == 1


def test_max_sequence_limit(temp_dir, sample_file):
    """Test maximum sequence number limit."""
    config = FileVersioningConfig(
        versioned_path=str(temp_dir),
        timestamp_format=TimestampSource.NOW,  # Use NOW to ensure same timestamp
    )
    versioning = FileVersioning(config)

    # Create a version with sequence 999
    timestamp = versioning._get_timestamp(Path(sample_file))
    max_version_path = temp_dir / f"test_file--{timestamp}_999.txt"
    max_version_path.touch()

    # Attempt to create another version with same timestamp
    with pytest.raises(VersionError) as exc_info:
        version_path = versioning.create_version(str(sample_file))  # noqa
    assert "Maximum sequence number (999) exceeded" in str(exc_info.value)


def test_remove_version_safety_checks(temp_dir, sample_file):
    """Test safety checks in remove_version method."""
    config = FileVersioningConfig(versioned_path=str(temp_dir / "versions"))
    versioning = FileVersioning(config)

    # Create a valid version first
    version_path = versioning.create_version(str(sample_file))

    # Test 1: Attempting to remove a file outside versions directory
    with pytest.raises(VersionError) as exc_info:
        versioning.remove_version(str(sample_file))
    assert "not in the versioned directory" in str(exc_info.value)

    # Test 2: Attempting to remove a file with invalid version pattern
    invalid_file = temp_dir / "versions" / "test_file_invalid.txt"
    invalid_file.touch()
    with pytest.raises(VersionError) as exc_info:
        versioning.remove_version(str(invalid_file))
    assert "does not follow the version naming pattern" in str(exc_info.value)

    # Test 3: Attempting to remove a file with partial version pattern
    partial_file = temp_dir / "versions" / "test_file--invalid.txt"
    partial_file.touch()
    with pytest.raises(VersionError) as exc_info:
        versioning.remove_version(str(partial_file))
    assert "does not follow the version naming pattern" in str(exc_info.value)

    # Test 4: Successfully remove a valid version file
    versioning.remove_version(version_path)
    assert not Path(version_path).exists()


def test_remove_version_nonexistent(temp_dir):
    """Test removing a nonexistent version file."""
    config = FileVersioningConfig(versioned_path=str(temp_dir))
    versioning = FileVersioning(config)

    nonexistent_path = temp_dir / "nonexistent--20240101.120000_001.txt"
    with pytest.raises(FileNotFoundError) as exc_info:
        versioning.remove_version(str(nonexistent_path))
    assert "does not exist" in str(exc_info.value)


@pytest.mark.parametrize(
    "compression_type",
    [CompressionType.NONE, CompressionType.GZIP, CompressionType.BZ2, CompressionType.XZ],
)
def test_compression_types(temp_dir, sample_file, compression_type):
    """Test different compression types with sequence numbers."""
    config = FileVersioningConfig(versioned_path=str(temp_dir), compression=compression_type)
    versioning = FileVersioning(config)

    version_path = versioning.create_version(str(sample_file))
    assert Path(version_path).exists()

    # Verify sequence number in filename
    assert "_001" in Path(version_path).name

    # Test file content after compression/decompression
    restore_path = temp_dir / "restored.txt"
    versioning.restore_version(version_path, str(restore_path))

    with restore_path.open("r") as f:
        content = f.read()
    assert content == "Test content"


@pytest.mark.parametrize(
    "test_params",
    [
        # Standard case: keep last 3 of 5
        {"max_count": 3, "num_versions": 5, "expected_sequences": [3, 4, 5]},
        # Minimal case: keep only latest
        {"max_count": 1, "num_versions": 3, "expected_sequences": [3]},
        # More slots than versions
        {"max_count": 5, "num_versions": 3, "expected_sequences": [1, 2, 3]},
        # No limit case
        {"max_count": None, "num_versions": 5, "expected_sequences": [1, 2, 3, 4, 5]},
        # Keep last 2 of 5
        {"max_count": 2, "num_versions": 5, "expected_sequences": [4, 5]},
    ],
)
def test_max_versions(temp_dir, sample_file, test_params):
    """Test max_count functionality with various scenarios.

    Tests multiple combinations of max_count and number of versions:
    - Standard case with keeping last N of M versions
    - Minimal case keeping only the latest version
    - Case where max_count is larger than number of versions
    - No limit case (max_count=None)
    - Different combinations of max_count and version counts
    """
    config = FileVersioningConfig(
        versioned_path=str(temp_dir),
        max_count=test_params["max_count"],
        timestamp_format=TimestampSource.NOW,  # Use NOW to ensure same timestamp
    )
    versioning = FileVersioning(config)

    # Create specified number of versions
    version_paths = []
    for _ in range(test_params["num_versions"]):
        version_path = versioning.create_version(str(sample_file))
        version_paths.append(version_path)

    # Get all versions using internal method to ensure correct sorting
    versions = versioning._get_versions(Path(sample_file))

    # Verify we have the expected number of versions
    assert len(versions) == len(
        test_params["expected_sequences"]
    ), f"Expected {len(test_params['expected_sequences'])} versions, got {len(versions)}"

    # Verify the sequence numbers of kept versions are correct
    sequences = []
    for version in versions:
        _, _, seq = versioning._parse_version_filename(version.name)
        sequences.append(seq)
    assert (
        sorted(sequences) == test_params["expected_sequences"]
    ), f"Expected sequences {test_params['expected_sequences']}, got {sorted(sequences)}"


@pytest.mark.parametrize("timezone_format", [TimezoneFormat.UTC, TimezoneFormat.LOCAL])
def test_timezone_formats(temp_dir, sample_file, timezone_format):
    """Test different timezone formats with sequence numbers."""
    config = FileVersioningConfig(
        versioned_path=str(temp_dir),
        timezone_format=timezone_format,
        timestamp_format=TimestampSource.NOW,
    )
    versioning = FileVersioning(config)

    version_path = versioning.create_version(str(sample_file))
    filename = Path(version_path).name

    # Verify basic format
    assert "_001" in filename
    current_time = datetime.now()
    if timezone_format == TimezoneFormat.UTC:
        current_time = current_time.astimezone(timezone.utc)
    timestamp_str = current_time.strftime("%Y%m%d")
    assert timestamp_str in filename


def test_duplicate_timestamp_handling(temp_dir, sample_file):
    """Test handling of duplicate timestamps."""
    config = FileVersioningConfig(versioned_path=str(temp_dir), timestamp_format=TimestampSource.NOW)
    versioning = FileVersioning(config)

    # Create multiple versions with the same timestamp
    versions = []
    for _ in range(3):
        version_path = versioning.create_version(str(sample_file))
        versions.append(Path(version_path))

    # Get unique timestamps
    timestamps = set()
    for version in versions:
        _, timestamp, _ = versioning._parse_version_filename(version.name)
        timestamps.add(timestamp)

    # Should have same timestamp but different sequence numbers
    assert len(timestamps) == 1  # Same timestamp
    assert len(versions) == 3  # Different versions

    # Verify sequence numbers are sequential
    sequences = []
    for version in versions:
        _, _, seq = versioning._parse_version_filename(version.name)
        sequences.append(seq)
    assert sorted(sequences) == [1, 2, 3]


def test_unicode_filenames(temp_dir, unicode_file):
    """Test handling of Unicode filenames with sequence numbers."""
    config = FileVersioningConfig(versioned_path=str(temp_dir))
    versioning = FileVersioning(config)

    version_path = versioning.create_version(str(unicode_file))
    assert Path(version_path).exists()
    assert "_001" in Path(version_path).name

    restore_path = temp_dir / "restored_unicode.txt"
    versioning.restore_version(version_path, str(restore_path))

    with restore_path.open("r") as f:
        content = f.read()
    assert content == "Unicode test content"


def test_relative_paths(temp_dir, sample_file):
    """Test handling of relative paths with sequence numbers."""
    original_dir = os.getcwd()
    os.chdir(str(temp_dir))

    try:
        config = FileVersioningConfig(versioned_path="versions")
        versioning = FileVersioning(config)

        relative_path = Path(sample_file).name
        version_path = versioning.create_version(relative_path)
        assert Path(version_path).exists()
        assert "_001" in Path(version_path).name

        restore_path = "restored.txt"
        versioning.restore_version(version_path, restore_path)
        assert Path(restore_path).exists()
    finally:
        os.chdir(original_dir)


def test_multiple_dots_in_filename(temp_dir):
    """Test handling of filenames with multiple dots."""
    file_path = temp_dir / "test.config.ini"
    with file_path.open("w") as f:
        f.write("Test content")

    config = FileVersioningConfig(versioned_path=str(temp_dir))
    versioning = FileVersioning(config)

    version_path = versioning.create_version(str(file_path))
    filename = Path(version_path).name

    # Verify the version maintains all dots and adds sequence number
    assert filename.startswith("test.config--")
    assert "_001.ini" in filename


def test_sequence_rollover(temp_dir, sample_file):
    """Test sequence number rollover prevention."""
    config = FileVersioningConfig(versioned_path=str(temp_dir))
    versioning = FileVersioning(config)

    # Create a version with sequence 999
    timestamp = versioning._get_timestamp(Path(sample_file))
    version_path = temp_dir / f"test_file--{timestamp}_999.txt"
    version_path.touch()

    # Attempt to create another version with same timestamp
    with pytest.raises(VersionError) as exc_info:
        version_path = versioning.create_version(str(sample_file))
    assert "Maximum sequence number (999) exceeded" in str(exc_info.value)


def test_list_versions(temp_dir, sample_file):
    """Test the list_versions public API."""
    config = FileVersioningConfig(
        versioned_path=str(temp_dir),
        compression=CompressionType.GZIP,
        timestamp_format=TimestampSource.NOW,  # Use NOW to ensure same timestamp
    )
    versioning = FileVersioning(config)

    # Create multiple versions
    version_paths = []
    for i in range(3):
        path = versioning.create_version(str(sample_file))
        version_paths.append(path)

    # Get list of versions
    versions = versioning.list_versions(str(sample_file))

    # Verify we got the right number of versions
    assert len(versions) == 3

    # Verify they're in reverse chronological order (newest first)
    assert versions[0].sequence > versions[1].sequence
    assert versions[1].sequence > versions[2].sequence

    # Verify version information
    for version in versions:
        # Check all fields are populated
        assert version.filename is not None
        assert version.original_name == "test_file"
        assert isinstance(version.timestamp, datetime)
        assert version.sequence in [1, 2, 3]
        assert version.size > 0
        assert version.compression == CompressionType.GZIP
        assert version.config == config


@pytest.mark.parametrize(
    "test_params",
    [
        # Test no compression
        {
            "filename": "test--20240101.120000_001.txt",
            "delimiter": "--",
            "expected": {"original_name": "test", "compression": CompressionType.NONE, "sequence": 1},
        },
        # Test gzip compression
        {
            "filename": "test--20240101.120000_002.txt.gz",
            "delimiter": "--",
            "expected": {"original_name": "test", "compression": CompressionType.GZIP, "sequence": 2},
        },
        # Test custom delimiter
        {
            "filename": "test##20240101.120000_003.txt",
            "delimiter": "##",
            "expected": {"original_name": "test", "compression": CompressionType.NONE, "sequence": 3},
        },
        # Test filename with dots
        {
            "filename": "test.config--20240101.120000_001.txt.gz",
            "delimiter": "--",
            "expected": {"original_name": "test.config", "compression": CompressionType.GZIP, "sequence": 1},
        },
    ],
)
def test_version_info(temp_dir, test_params):
    """Test VersionInfo class parsing and attributes."""
    # Create a dummy file with the test filename
    test_file = temp_dir / test_params["filename"]
    test_file.write_text("test content")

    # Create VersionInfo instance
    config = FileVersioningConfig(delimiter=test_params["delimiter"])
    version_info = VersionInfo(path=test_file, config=config)

    # Verify all expected values
    assert version_info.original_name == test_params["expected"]["original_name"]
    assert version_info.compression == test_params["expected"]["compression"]
    assert version_info.sequence == test_params["expected"]["sequence"]
    assert version_info.size > 0

    # Verify timestamp parsing
    assert isinstance(version_info.timestamp, datetime)
    assert version_info.timestamp.year == 2024
    assert version_info.timestamp.month == 1
    assert version_info.timestamp.day == 1
    assert version_info.timestamp.hour == 12
    assert version_info.timestamp.minute == 0
    assert version_info.timestamp.second == 0


@pytest.mark.parametrize(
    "invalid_filename",
    [
        "test.txt",  # No delimiter or version info
        "test--invalid.txt",  # Invalid timestamp format
        "test--20240101.120000.txt",  # Missing sequence number
        "test--20240101_001.txt",  # Invalid timestamp format
    ],
)
def test_version_info_invalid_filenames(temp_dir, invalid_filename):
    """Test VersionInfo class with invalid filenames."""
    test_file = temp_dir / invalid_filename
    test_file.write_text("test content")

    config = FileVersioningConfig()

    with pytest.raises(ValueError) as exc_info:
        VersionInfo(path=test_file, config=config)
    assert "Invalid version filename format" in str(exc_info.value)
