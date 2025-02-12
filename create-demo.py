#!/usr/bin/env python3

"""Demo script for py-file-versioning library.

This script demonstrates various features of the file versioning system
by creating example files and versions with different configurations.
"""

import os
from pathlib import Path

from py_file_versioning import FileVersioning, FileVersioningConfig


def create_example_file(filename: str) -> None:
    """Create a sample INI file with database settings.

    Args:
        filename: Name of the file to create
    """
    content = """
# Database configuration settings
db_host = db.example.com
db_port = 5432
db_name = production_db
db_user = app_user
db_pool_size = 10
db_timeout = 30
    """.strip()

    with open(filename, "w") as f:
        f.write(content)


def create_version_variations(filename: str) -> list[str]:
    """Create versions with different timezone and timestamp source combinations.

    Args:
        filename: Name of the file to version

    Returns:
        List of paths to created version files
    """
    versions = []

    # All combinations of timezone and timestamp source
    configs = [
        # Local timezone versions
        {"use_utc": False, "use_modified_time": True, "desc": "local timezone, modified time"},
        {"use_utc": False, "use_modified_time": False, "desc": "local timezone, current time"},
        # UTC timezone versions
        {"use_utc": True, "use_modified_time": True, "desc": "UTC timezone, modified time"},
        {"use_utc": True, "use_modified_time": False, "desc": "UTC timezone, current time"},
    ]

    for cfg in configs:
        config = FileVersioningConfig(use_utc=cfg["use_utc"], use_modified_time=cfg["use_modified_time"])
        versioning = FileVersioning(config)
        version_path, removed, error = versioning.create_version(filename)
        if error:
            print(f"Warning during version creation ({cfg['desc']}): {error}")
        versions.append((version_path, cfg["desc"]))

    return versions


def create_compressed_versions(filename: str):
    """Create versions using each compression type with varied timezone settings.

    Args:
        filename: Name of the file to version

    Returns:
        List of paths to created version files
    """
    versions = []
    compression_types = ["gz", "bz2", "xz"]

    for compression in compression_types:
        # Alternate between UTC and local time, and modified/current time
        use_utc = compression in ["bz2", "xz"]
        use_modified = compression in ["gz", "xz"]

        config = FileVersioningConfig(compression=compression, use_utc=use_utc, use_modified_time=use_modified)
        versioning = FileVersioning(config)
        version_path, removed, error = versioning.create_version(filename)
        if error:
            print(f"Warning during {compression} version creation: {error}")
        desc = f"{compression} compression, {'UTC' if use_utc else 'local'} timezone, {'modified' if use_modified else 'current'} time"
        versions.append((version_path, desc))

    return versions


def create_custom_backup_versions(filename: str):
    """Create versions in 'backups' directory with custom delimiter and varied settings.

    Args:
        filename: Name of the file to version

    Returns:
        List of paths to created version files
    """
    versions = []
    configs = [
        {"use_utc": True, "use_modified_time": False, "desc": "UTC timezone, current time"},
        {"use_utc": False, "use_modified_time": True, "desc": "local timezone, modified time"},
    ]

    for cfg in configs:
        config = FileVersioningConfig(
            versions_path="backups", delimiter="__", use_utc=cfg["use_utc"], use_modified_time=cfg["use_modified_time"]
        )
        versioning = FileVersioning(config)
        version_path, removed, error = versioning.create_version(filename)
        if error:
            print(f"Warning during backup version creation ({cfg['desc']}): {error}")
        versions.append((version_path, cfg["desc"]))

    return versions


def list_all_versions(filename: str, versions_path: str = "versions", delimiter: str = "--") -> None:
    """List all versions of the file.

    Args:
        filename: Name of the file to list versions for
        versions_path: Directory containing the versions (default: "versions")
        delimiter: The delimiter used in version filenames (default: "--")
    """
    config = FileVersioningConfig(versions_path=versions_path, delimiter=delimiter)
    versioning = FileVersioning(config)
    versions = versioning.list_versions(filename)

    print(f"\nVersions for {filename} in {versions_path}:")
    print("-" * 60)

    if not versions:
        print("No versions found")
        return

    print()  # Add blank line before table
    from texttable import Texttable

    table = Texttable()
    table.set_deco(Texttable.HEADER | Texttable.VLINES)
    table.set_max_width(0)
    table.set_cols_align(("l", "r", "r", "l", "r", "r"))
    table.set_cols_valign(("t", "t", "t", "t", "t", "t"))

    headers = ["Path", "Sequence", "Size", "Timestamp", "TimeZone", "TimestampSrc"]
    separator = ["=" * len(h) for h in headers]

    table.add_row(headers)
    table.add_row(separator)

    for version in versions:
        tz_fmt = "local" if version["timezone_fmt"] == "loc" else "utc"
        ts_src = "stored time" if version["timestamp_src"] == "sto" else "modify time"
        row = (Path(version["path"]).name, version["sequence"], version["size"], version["timestamp"], tz_fmt, ts_src)
        table.add_row(row)

    print(table.draw())


def main():
    """Main function demonstrating various versioning features."""
    filename = "example.ini"

    # Create the example file
    create_example_file(filename)
    print(f"Created example file: {filename}")

    # Create versions with different timezone and timestamp combinations
    print("\nCreating versions with different timezone and timestamp settings...")
    versions = create_version_variations(filename)
    for version_path, desc in versions:
        print(f"Created version ({desc}): {os.path.basename(version_path)}")

    # Create compressed versions with varied settings
    print("\nCreating compressed versions with varied settings...")
    compressed_versions = create_compressed_versions(filename)
    for version_path, desc in compressed_versions:
        print(f"Created version ({desc}): {os.path.basename(version_path)}")

    # Create backup versions with varied settings
    print("\nCreating backup versions with varied settings...")
    backup_versions = create_custom_backup_versions(filename)
    for version_path, desc in backup_versions:
        print(f"Created backup version ({desc}): {os.path.basename(version_path)}")

    # List all versions from both directories
    list_all_versions(filename)  # List versions in default directory
    list_all_versions(filename, "backups", "__")  # List versions in backups directory


if __name__ == "__main__":
    main()
