"""Tests for file versioning system."""

import os
from datetime import datetime
from pathlib import Path
from typing import Generator

import pytest

from py_file_versioning.versioning import FileVersioning, FileVersioningConfig


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


@pytest.fixture
def versions_dir(temp_dir: Path) -> Generator[Path, None, None]:
    """Creates a versions directory for testing."""
    versions_path = temp_dir / "versions"
    versions_path.mkdir(exist_ok=True)
    yield versions_path
    if versions_path.exists():
        for f in versions_path.iterdir():
            f.unlink()
        versions_path.rmdir()


class TestFileVersioningConfig:
    """Tests for FileVersioningConfig."""

    def test_default_config(self) -> None:
        """Tests default configuration values."""
        config = FileVersioningConfig()
        assert str(config) == (
            "FileVersioningConfig(\n"
            "    delimiter: '--'\n"
            "    timezone: local\n"
            "    versions_path: 'versions'\n"
            "    compression: 'none'\n"
            "    max_versions: unlimited\n"
            "    timestamp_source: modified time\n"
            ")"
        )

    def test_custom_config(self) -> None:
        """Tests custom configuration values."""
        config = FileVersioningConfig(
            delimiter="__",
            use_utc=True,
            versions_path="backup",
            compression="gz",
            max_versions=5,
            use_modified_time=False,
        )
        assert "__" in str(config)
        assert "UTC" in str(config)
        assert "backup" in str(config)
        assert "gz" in str(config)
        assert "5" in str(config)
        assert "stored time" in str(config)

    def test_invalid_config(self) -> None:
        """Tests invalid configuration values."""
        with pytest.raises(ValueError):
            FileVersioningConfig(max_versions=-1)

        with pytest.raises(ValueError):
            FileVersioningConfig(compression="invalid")

        with pytest.raises(ValueError):
            FileVersioningConfig(delimiter="")


class TestFileVersioning:
    """Tests for FileVersioning."""

    @pytest.fixture
    def versioning(self, versions_dir: Path) -> FileVersioning:
        """Creates a FileVersioning instance for testing."""
        config = FileVersioningConfig(versions_path=str(versions_dir))
        return FileVersioning(config)

    def test_create_version_basic(self, versioning: FileVersioning, sample_file: Path) -> None:
        """Tests basic version creation."""
        version_path, removed, error = versioning.create_version(sample_file)
        assert version_path
        assert Path(version_path).exists()
        assert removed == 0  # No cleanup needed for first version
        assert not error
        assert Path(version_path).read_text() == "Test content"

    def test_create_version_with_compression(self, versions_dir: Path, sample_file: Path) -> None:
        """Tests version creation with compression."""
        config = FileVersioningConfig(versions_path=str(versions_dir), compression="gz")
        versioning = FileVersioning(config)
        version_path, removed, error = versioning.create_version(sample_file)
        assert version_path.endswith(".gz")
        assert Path(version_path).exists()
        assert Path(version_path).stat().st_size > 0

    def test_create_version_nonexistent_file(self, versioning: FileVersioning) -> None:
        """Tests creating version of nonexistent file."""
        with pytest.raises(FileNotFoundError):
            versioning.create_version("nonexistent.txt")

    def test_create_multiple_versions(self, versioning: FileVersioning, sample_file: Path) -> None:
        """Tests creating multiple versions of the same file."""
        # Create first version
        version1, _, _ = versioning.create_version(sample_file)

        # Modify file and create second version
        sample_file.write_text("Modified content")
        version2, _, _ = versioning.create_version(sample_file)

        assert Path(version1) != Path(version2)
        assert Path(version1).exists()
        assert Path(version2).exists()

    def test_list_versions(self, versioning: FileVersioning, sample_file: Path) -> None:
        """Tests listing versions."""
        # Create multiple versions
        version1, _, _ = versioning.create_version(sample_file)
        sample_file.write_text("Modified content")
        version2, _, _ = versioning.create_version(sample_file)

        versions = versioning.list_versions(sample_file)
        assert len(versions) == 2
        assert isinstance(versions[0]["timestamp"], str)
        assert isinstance(versions[0]["size"], int)
        assert isinstance(versions[0]["sequence"], int)
        # Check if versions are sorted newest to oldest
        timestamp1 = datetime.fromisoformat(versions[0]["timestamp"])
        timestamp2 = datetime.fromisoformat(versions[1]["timestamp"])
        assert timestamp1 >= timestamp2

    def test_restore_version(self, versioning: FileVersioning, sample_file: Path, temp_dir: Path) -> None:
        """Tests version restoration."""
        # Create a version
        version_path, _, _ = versioning.create_version(sample_file)
        original_content = sample_file.read_text()

        # Modify the original file
        sample_file.write_text("Modified content")
        assert sample_file.read_text() != original_content

        # Restore the version
        restored_path = temp_dir / "restored.txt"
        versioning.restore_version(version_path, restored_path)
        assert restored_path.read_text() == original_content

    def test_restore_nonexistent_version(self, versioning: FileVersioning, temp_dir: Path) -> None:
        """Tests restoring nonexistent version."""
        with pytest.raises(FileNotFoundError):
            versioning.restore_version("nonexistent.txt", temp_dir / "restored.txt")

    def test_remove_version(self, versioning: FileVersioning, sample_file: Path) -> None:
        """Tests version removal."""
        version_path, _, _ = versioning.create_version(sample_file)
        assert Path(version_path).exists()
        versioning.remove_version(version_path)
        assert not Path(version_path).exists()

    def test_remove_nonexistent_version(self, versioning: FileVersioning) -> None:
        """Tests removing nonexistent version."""
        with pytest.raises(FileNotFoundError):
            versioning.remove_version("nonexistent.txt")

    def test_versioning_with_max_versions(self, versions_dir: Path, sample_file: Path) -> None:
        """Tests version cleanup with max_versions set."""
        config = FileVersioningConfig(versions_path=str(versions_dir), max_versions=2)
        versioning = FileVersioning(config)

        # Create three versions
        paths = []
        for i in range(3):
            sample_file.write_text(f"Content version {i}")
            path, removed, error = versioning.create_version(sample_file)
            paths.append(path)
            if i < 2:
                assert removed == 0  # No cleanup needed yet
            else:
                assert removed == 1  # One old version should be removed

        # Check that only the latest two versions exist
        assert not Path(paths[0]).exists()  # Oldest version should be removed
        assert Path(paths[1]).exists()
        assert Path(paths[2]).exists()

    def test_version_filename_components(self, versioning: FileVersioning, sample_file: Path) -> None:
        """Tests version filename format and components."""
        version_path, _, _ = versioning.create_version(sample_file)
        filename = Path(version_path).name

        # Check filename components
        assert versioning.config.delimiter in filename
        parts = filename.split(versioning.config.delimiter)
        assert len(parts) == 3
        assert parts[0] == sample_file.stem

        # Check timestamp and sequence format
        version_info = parts[1]
        assert len(version_info) >= 19  # YYYYMMDD.HHMMSS_NNN
        assert "." in version_info
        assert "_" in version_info

        # Check version spec format
        spec = parts[2].split(".")[0]  # Remove extension
        assert "_" in spec
        assert spec.startswith(("utc", "loc"))
        assert spec.endswith(("mod", "sto"))


class TestEdgeCases:
    """Tests for edge cases and error conditions."""

    def test_create_version_in_nonexistent_directory(self, temp_dir: Path, sample_file: Path) -> None:
        """Tests creating version in nonexistent directory."""
        nonexistent_dir = temp_dir / "nonexistent"
        config = FileVersioningConfig(versions_path=str(nonexistent_dir))
        versioning = FileVersioning(config)
        version_path, _, _ = versioning.create_version(sample_file)
        assert Path(version_path).exists()
        assert nonexistent_dir.exists()

    @pytest.fixture
    def versioning(self, versions_dir: Path) -> FileVersioning:
        """Creates a FileVersioning instance for testing."""
        config = FileVersioningConfig(versions_path=str(versions_dir))
        return FileVersioning(config)

    def test_restore_to_existing_file(self, versioning: FileVersioning, sample_file: Path, temp_dir: Path) -> None:
        """Tests restoring version to existing file."""
        # Create a version
        version_path, _, _ = versioning.create_version(sample_file)

        # Create existing file at restore location
        restore_path = temp_dir / "existing.txt"
        restore_path.write_text("Existing content")

        # Restore should overwrite existing file
        versioning.restore_version(version_path, restore_path)
        assert restore_path.read_text() == "Test content"

    def test_mixed_timezone_formats(self, versions_dir: Path, sample_file: Path) -> None:
        """Tests handling of mixed timezone formats."""
        # Create version with local time
        local_config = FileVersioningConfig(versions_path=str(versions_dir), use_utc=False, max_versions=5)  # Enable version checking
        local_versioning = FileVersioning(local_config)
        local_versioning.create_version(sample_file)

        # Try to create version with UTC time
        utc_config = FileVersioningConfig(versions_path=str(versions_dir), use_utc=True, max_versions=5)  # Enable version checking
        utc_versioning = FileVersioning(utc_config)
        _, _, error = utc_versioning.create_version(sample_file)
        assert "Multiple timezone types not allowed" in error

    def test_mixed_timestamp_sources(self, versions_dir: Path, sample_file: Path) -> None:
        """Tests handling of mixed timestamp sources."""
        # Create version with modified time
        mod_config = FileVersioningConfig(
            versions_path=str(versions_dir), use_modified_time=True, max_versions=5  # Enable version checking
        )
        mod_versioning = FileVersioning(mod_config)
        mod_versioning.create_version(sample_file)

        # Try to create version with stored time
        stored_config = FileVersioningConfig(
            versions_path=str(versions_dir), use_modified_time=False, max_versions=5  # Enable version checking
        )
        stored_versioning = FileVersioning(stored_config)
        _, _, error = stored_versioning.create_version(sample_file)
        assert "Multiple source types not allowed" in error

    def test_sequence_number_increment(self, versioning: FileVersioning, sample_file: Path) -> None:
        """Tests sequence number increments correctly for same timestamp."""
        paths = []
        # Create multiple versions quickly to get same timestamp
        for _ in range(3):
            path, _, _ = versioning.create_version(sample_file)
            paths.append(path)

        # Extract and check sequence numbers
        sequences = []
        for path in paths:
            filename = Path(path).name
            seq_part = filename.split(versioning.config.delimiter)[1].split("_")[1]
            sequences.append(int(seq_part))

        assert sequences == [1, 2, 3]  # Should increment regardless of timestamp
