#!/usr/bin/env python3

import hashlib
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path


def run_command(cmd: list[str]) -> tuple[int, str, str]:
    """Run a shell command and return exit code, stdout, and stderr."""
    process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    stdout, stderr = process.communicate()
    return process.returncode, stdout, stderr


def get_file_hash(file_path: str) -> str:
    """Calculate SHA256 hash of a file."""
    sha256 = hashlib.sha256()
    with open(file_path, "rb") as f:
        for block in iter(lambda: f.read(4096), b""):
            sha256.update(block)
    return sha256.hexdigest()


def main():
    PGM_NAME = "pyfileversioning"
    # Create a temporary directory for testing
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_dir_path = Path(temp_dir)
        versions_dir = temp_dir_path / "versions"
        test_file = temp_dir_path / "test.txt"
        restored_file = temp_dir_path / "restored.txt"

        print(f"\n{'='*60}")
        print(f"Starting CLI integration test at {datetime.now()}")
        print(f"{'='*60}")
        print(f"Test directory: {temp_dir}")

        # Create test file with content
        test_content = "This is test content\nLine 2\nLine 3\n"
        test_file.write_text(test_content)
        original_hash = get_file_hash(str(test_file))
        print(f"\nCreated test file: {test_file}")
        print(f"Original hash: {original_hash}")

        # Test different compression types
        compression_types = ["none", "gzip", "bz2", "xz"]
        for compression in compression_types:
            print(f"\nTesting {compression} compression:")
            print("-" * 30)

            # Create version with compression
            cmd = [
                PGM_NAME,
                "create",
                str(test_file),
                "--compression",
                compression,
                "--versions-dir",
                str(versions_dir),
            ]
            rc, stdout, stderr = run_command(cmd)
            if rc != 0:
                print(f"Error creating version with {compression} compression:")
                print(stderr)
                continue
            print(f"Created version: {stdout.strip()}")

            # List versions
            cmd = [PGM_NAME, "list", str(test_file), "--versions-dir", str(versions_dir)]
            rc, stdout, stderr = run_command(cmd)
            if rc != 0:
                print("Error listing versions:")
                print(stderr)
                continue
            print(f"Version listing:\n{stdout}")

            # Get the version file path from stdout
            # Find the last line with file info (containing 'bytes')
            file_lines = [line for line in stdout.strip().split("\n") if "bytes" in line]
            if not file_lines:
                print("Error: No version information found in output")
                continue
            version_file = file_lines[-1].split()[0]
            version_path = versions_dir / version_file

            # Restore version
            cmd = [
                PGM_NAME,
                "restore",
                str(version_path),
                "--target",
                str(restored_file),
                "--versions-dir",
                str(versions_dir),
            ]
            rc, stdout, stderr = run_command(cmd)
            if rc != 0:
                print("Error restoring version:")
                print(stderr)
                continue
            print(f"Restored to: {restored_file}")

            # Verify restored content
            restored_hash = get_file_hash(str(restored_file))
            if restored_hash == original_hash:
                print("✓ Hash verification successful")
            else:
                print("× Hash verification failed!")
                print(f"Expected: {original_hash}")
                print(f"Got:      {restored_hash}")

            # Clean up restored file
            restored_file.unlink(missing_ok=True)

        # Test max versions feature
        print("\nTesting max versions feature:")
        print("-" * 30)

        # Create multiple versions with max_versions=3
        for i in range(5):
            test_file.write_text(f"Content version {i+1}\n")
            cmd = [
                PGM_NAME,
                "create",
                str(test_file),
                "--versions-dir",
                str(versions_dir),
                "--max-versions",
                "3",
                "--timestamp-source",
                "now",
            ]
            rc, stdout, stderr = run_command(cmd)
            if rc != 0:
                print(f"Error creating version {i+1}:")
                print(stderr)
                continue
            print(f"Created version {i+1}: {stdout.strip()}")

        # Get the number of versions directly from the CLI tool output
        cmd = [
            PGM_NAME,
            "list",
            str(test_file),
            "--versions-dir",
            str(versions_dir),
            "--timestamp-source",
            "now",
        ]
        rc, stdout, stderr = run_command(cmd)
        if rc == 0:
            # Count lines containing version info (has filename and bytes)
            version_lines = [line for line in stdout.split("\n") if line.strip() and "bytes" in line and "_" in line]
            version_count = len(version_lines)
            if version_count == 3:
                print(f"✓ Max versions test successful (kept {version_count} versions)")
            else:
                print(f"× Max versions test failed (kept {version_count} versions, expected 3)")
            if version_count > 0:
                print("Last version info:", version_lines[-1])

        # Test remove version safety checks
        print("\nTesting remove version safety checks:")
        print("-" * 30)

        # Create a test version to work with
        test_file.write_text("Content for remove tests\n")
        cmd = [
            PGM_NAME,
            "create",
            str(test_file),
            "--versions-dir",
            str(versions_dir),
        ]
        rc, stdout, stderr = run_command(cmd)
        version_path = Path(stdout.strip().split(": ")[-1])

        # Test 1: Try to remove a file outside versions directory
        print("\nTest 1: Attempt to remove file outside versions directory")
        cmd = [PGM_NAME, "remove", str(test_file), "--versions-dir", str(versions_dir)]
        rc, stdout, stderr = run_command(cmd)
        if rc != 0 and "not in the versioned directory" in stderr:
            print("✓ Successfully blocked removal of file outside versions directory")
        else:
            print("× Failed to block removal of file outside versions directory")

        # Test 2: Try to remove a file with invalid version pattern
        print("\nTest 2: Attempt to remove file with invalid version pattern")
        invalid_file = versions_dir / "test_invalid.txt"
        invalid_file.write_text("invalid")
        cmd = [PGM_NAME, "remove", str(invalid_file), "--versions-dir", str(versions_dir)]
        rc, stdout, stderr = run_command(cmd)
        if rc != 0 and "does not follow the version naming pattern" in stderr:
            print("✓ Successfully blocked removal of file with invalid pattern")
        else:
            print("× Failed to block removal of file with invalid pattern")

        # Test 3: Remove a valid version file
        print("\nTest 3: Remove valid version file")
        cmd = [PGM_NAME, "remove", str(version_path), "--versions-dir", str(versions_dir)]
        rc, stdout, stderr = run_command(cmd)
        if rc == 0 and not version_path.exists():
            print("✓ Successfully removed valid version file")
        else:
            print("× Failed to remove valid version file")

        # Test 4: Try to remove a nonexistent file
        print("\nTest 4: Attempt to remove nonexistent file")
        nonexistent = versions_dir / "nonexistent--20240101.120000_001.txt"
        cmd = [PGM_NAME, "remove", str(nonexistent), "--versions-dir", str(versions_dir)]
        rc, stdout, stderr = run_command(cmd)
        if rc != 0 and "does not exist" in stderr:
            print("✓ Successfully handled nonexistent file")
        else:
            print("× Failed to handle nonexistent file")

        print(f"\n{'='*60}")
        print("Integration test complete")
        print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
