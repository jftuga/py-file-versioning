"""Tests for the command-line interface."""

import os
from pathlib import Path
from typing import Generator, List

import pytest

from py_file_versioning.pyfileversioning import (
    FileVersioning,
    FileVersioningConfig,
    expand_file_patterns,
    main,
    parse_args,
)


@pytest.fixture
def temp_dir(tmp_path: Path) -> Generator[Path, None, None]:
    """Creates a temporary directory for testing."""
    cwd = os.getcwd()
    os.chdir(tmp_path)
    yield tmp_path
    os.chdir(cwd)


@pytest.fixture
def sample_files(temp_dir: Path) -> Generator[List[Path], None, None]:
    """Creates sample files for testing."""
    files = []
    for i in range(3):
        file_path = temp_dir / f"test{i}.txt"
        file_path.write_text(f"Test content {i}")
        files.append(file_path)
    yield files
    for file in files:
        if file.exists():
            file.unlink()


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


class TestCommandLineArguments:
    """Tests for command line argument parsing."""

    def test_version_flag(self) -> None:
        """Tests --version flag."""
        args = parse_args(["--version"])
        assert args.version is True

    def test_required_command(self) -> None:
        """Tests command is required."""
        with pytest.raises(SystemExit):
            main([])

    @pytest.mark.parametrize("command", ["create", "restore", "list", "remove"])
    def test_valid_commands(self, command: str) -> None:
        """Tests all valid commands."""
        args = parse_args([command, "file.txt"])
        assert args.command == command

    def test_invalid_command(self) -> None:
        """Tests invalid command."""
        with pytest.raises(SystemExit):
            parse_args(["invalid", "file.txt"])

    def test_compression_options(self) -> None:
        """Tests compression options."""
        for compression in ["none", "gz", "bz2", "xz"]:
            args = parse_args(["create", "file.txt", "-c", compression])
            assert args.compression == compression

    def test_invalid_compression(self) -> None:
        """Tests invalid compression option."""
        with pytest.raises(SystemExit):
            parse_args(["create", "file.txt", "-c", "invalid"])

    def test_utc_flag(self) -> None:
        """Tests UTC timezone flag."""
        args = parse_args(["create", "file.txt", "--utc"])
        assert args.utc is True

    def test_max_versions(self) -> None:
        """Tests max versions option."""
        args = parse_args(["create", "file.txt", "-m", "5"])
        assert args.max_versions == 5

    def test_invalid_max_versions(self) -> None:
        """Tests invalid max versions value."""
        with pytest.raises(SystemExit):
            parse_args(["create", "file.txt", "-m", "invalid"])

    def test_source_options(self) -> None:
        """Tests timestamp source options."""
        for src in ["mod", "sto"]:
            args = parse_args(["create", "file.txt", "-s", src])
            assert args.src == src

    def test_invalid_source(self) -> None:
        """Tests invalid timestamp source."""
        with pytest.raises(SystemExit):
            parse_args(["create", "file.txt", "-s", "invalid"])

    def test_delimiter_option(self) -> None:
        """Tests delimiter option."""
        args = parse_args(["create", "file.txt", "-D", "++"])
        assert args.delimiter == "++"


class TestFileOperations:
    """Tests for file operations."""

    def test_create_version(self, temp_dir: Path, sample_files: List[Path], capsys: pytest.CaptureFixture) -> None:
        """Tests version creation."""
        main(["create", str(sample_files[0])])
        captured = capsys.readouterr()
        assert "Created version:" in captured.out
        assert "versions" in captured.out

    def test_create_version_with_compression(self, temp_dir: Path, sample_files: List[Path], capsys: pytest.CaptureFixture) -> None:
        """Tests version creation with compression."""
        main(["create", str(sample_files[0]), "-c", "gz"])
        captured = capsys.readouterr()
        assert "Created version:" in captured.out
        assert ".gz" in captured.out

    def test_list_versions(self, temp_dir: Path, sample_files: List[Path], capsys: pytest.CaptureFixture) -> None:
        """Tests version listing."""
        # Create a version first
        main(["create", str(sample_files[0])])

        # List versions
        main(["list", str(sample_files[0])])
        captured = capsys.readouterr()
        assert "Path" in captured.out
        assert "Sequence" in captured.out
        assert "Timestamp" in captured.out

    def test_remove_version(self, temp_dir: Path, sample_files: List[Path], capsys: pytest.CaptureFixture) -> None:
        """Tests version removal."""
        # Create a version
        main(["create", str(sample_files[0])])
        captured = capsys.readouterr()
        version_path = captured.out.split(": ")[1].strip()

        # Remove the version
        main(["remove", version_path])
        captured = capsys.readouterr()
        assert "Removed version:" in captured.out
        assert not Path(version_path).exists()

    def test_restore_version(self, temp_dir: Path, sample_files: List[Path], capsys: pytest.CaptureFixture) -> None:
        """Tests version restoration."""
        # Create a version
        main(["create", str(sample_files[0])])
        captured = capsys.readouterr()
        version_path = captured.out.split(": ")[1].strip()

        # Modify original file
        sample_files[0].write_text("Modified content")

        # Restore version
        restore_path = temp_dir / "restored.txt"
        main(["restore", version_path, "-t", str(restore_path)])
        captured = capsys.readouterr()
        assert "Restored" in captured.out
        assert restore_path.read_text() == "Test content 0"


class TestPatternExpansion:
    """Tests for file pattern expansion."""

    def test_single_file(self, temp_dir: Path, sample_files: List[Path]) -> None:
        """Tests single file pattern."""
        expanded = expand_file_patterns([str(sample_files[0])])
        assert len(expanded) == 1
        assert expanded[0] == sample_files[0]

    def test_wildcard_pattern(self, temp_dir: Path, sample_files: List[Path]) -> None:
        """Tests wildcard pattern expansion."""
        expanded = expand_file_patterns([str(temp_dir / "*.txt")])
        assert len(expanded) == 3
        assert all(f.suffix == ".txt" for f in expanded)

    def test_multiple_patterns(self, temp_dir: Path, sample_files: List[Path]) -> None:
        """Tests multiple pattern expansion."""
        patterns = [str(temp_dir / "test0.txt"), str(temp_dir / "test1.txt")]
        expanded = expand_file_patterns(patterns)
        assert len(expanded) == 2
        assert {f.name for f in expanded} == {"test0.txt", "test1.txt"}

    def test_nonexistent_pattern(self, temp_dir: Path) -> None:
        """Tests nonexistent file pattern."""
        with pytest.raises(SystemExit):
            main(["create", str(temp_dir / "nonexistent*.txt")])


class TestEnvironmentVariables:
    """Tests for environment variable handling."""

    def test_versions_path_env(self, temp_dir: Path, sample_files: List[Path], monkeypatch: pytest.MonkeyPatch) -> None:
        """Tests PFV_VERSIONS_PATH environment variable."""
        custom_path = str(temp_dir / "custom_versions")
        monkeypatch.setenv("PFV_VERSIONS_PATH", custom_path)
        args = parse_args(["create", str(sample_files[0])])
        assert args.versions_path == custom_path

    def test_compression_env(self, temp_dir: Path, sample_files: List[Path], monkeypatch: pytest.MonkeyPatch) -> None:
        """Tests PFV_COMPRESSION environment variable."""
        monkeypatch.setenv("PFV_COMPRESSION", "gz")
        args = parse_args(["create", str(sample_files[0])])
        assert args.compression == "gz"

    def test_delimiter_env(self, temp_dir: Path, sample_files: List[Path], monkeypatch: pytest.MonkeyPatch) -> None:
        """Tests PFV_DELIMITER environment variable."""
        monkeypatch.setenv("PFV_DELIMITER", "++")
        args = parse_args(["create", str(sample_files[0])])
        assert args.delimiter == "++"


class TestErrorHandling:
    """Tests for error handling."""

    def test_nonexistent_file(self, temp_dir: Path, capsys: pytest.CaptureFixture) -> None:
        """Tests handling of nonexistent file."""
        with pytest.raises(SystemExit):
            main(["create", "nonexistent.txt"])
        captured = capsys.readouterr()
        assert "Error" in captured.err

    def test_restore_without_target(self, temp_dir: Path, sample_files: List[Path], capsys: pytest.CaptureFixture) -> None:
        """Tests restore without target path."""
        with pytest.raises(SystemExit):
            main(["restore", str(sample_files[0])])
        captured = capsys.readouterr()
        assert "Error: --target required" in captured.out

    def test_invalid_version_file(self, temp_dir: Path, sample_files: List[Path], capsys: pytest.CaptureFixture) -> None:
        """Tests handling of invalid version file."""
        with pytest.raises(SystemExit):
            main(["remove", "invalid_version.txt"])
        captured = capsys.readouterr()
        assert "Error" in captured.err


class TestVersionListing:
    """Tests for version listing functionality."""

    def test_no_versions(self, temp_dir: Path, sample_files: List[Path], capsys: pytest.CaptureFixture) -> None:
        """Tests listing when no versions exist."""
        main(["list", str(sample_files[0])])
        captured = capsys.readouterr()
        assert "No versions found" in captured.out

    def test_multiple_versions(self, temp_dir: Path, sample_files: List[Path], capsys: pytest.CaptureFixture) -> None:
        """Tests listing multiple versions."""
        # Create multiple versions
        for _ in range(3):
            main(["create", str(sample_files[0])])
            sample_files[0].write_text(f"Modified content {_}")

        main(["list", str(sample_files[0])])
        captured = capsys.readouterr()
        assert "Path" in captured.out
        assert "Sequence" in captured.out
        assert "Timestamp" in captured.out
        # Count number of versions listed
        assert len(captured.out.strip().split("\n")) >= 5  # Header + separator + 3 versions


class TestVersionCleanup:
    """Tests for version cleanup functionality."""

    def test_max_versions(self, temp_dir: Path, sample_files: List[Path], capsys: pytest.CaptureFixture) -> None:
        """Tests max versions limit."""
        config = FileVersioningConfig(versions_path=str(temp_dir / "versions"), max_versions=2)
        versioning = FileVersioning(config)

        for i in range(3):
            sample_files[0].write_text(f"Content {i}")
            versioning.create_version(sample_files[0])

        # List versions directly using FileVersioning API
        versions = versioning.list_versions(sample_files[0])
        assert len(versions) == 2, "Should only have 2 versions"

        # Verify through CLI as well
        main(["list", str(sample_files[0]), "-d", str(temp_dir / "versions")])
        captured = capsys.readouterr()
        # Count non-empty lines, excluding headers and separators
        version_lines = [line for line in captured.out.split("\n") if line.strip() and "test0" in line]
        assert len(version_lines) == 2, "CLI should show 2 versions"
