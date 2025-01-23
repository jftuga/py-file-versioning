#!/usr/bin/env python3

import os
from py_file_versioning import FileVersioning, FileVersioningConfig, CompressionType, TimestampSource


def create_example_file(filename: str) -> None:
    """Create a sample INI file with database settings."""
    content = """
# Database configuration settings
db_host = db.example.com
db_port = 5432
db_name = production_db
db_user = app_user
db_pool_size = 10
db_timeout = 30
    """.strip()

    with open(filename, 'w') as f:
        f.write(content)


def create_default_version(filename: str) -> str:
    """Create a version using default settings."""
    versioning = FileVersioning()
    return versioning.create_version(filename)


def create_custom_backup_version(filename: str) -> str:
    """Create a version in 'backups' directory with custom delimiter."""
    config = FileVersioningConfig(
        versioned_path="backups",  # Use backups directory
        delimiter="__"             # Use double underscore delimiter
    )
    versioning = FileVersioning(config)
    return versioning.create_version(filename)


def create_compressed_versions(filename: str) -> list[str]:
    """Create versions using each compression type."""
    versions = []
    
    compression_types = [
        CompressionType.GZIP,
        CompressionType.BZ2,
        CompressionType.XZ
    ]
    
    for compression in compression_types:
        config = FileVersioningConfig(compression=compression)
        versioning = FileVersioning(config)
        version_path = versioning.create_version(filename)
        versions.append(version_path)
    
    return versions


def create_now_timestamp_version(filename: str) -> str:
    """Create a version using 'now' as timestamp source."""
    config = FileVersioningConfig(timestamp_format=TimestampSource.NOW)
    versioning = FileVersioning(config)
    return versioning.create_version(filename)


def list_all_versions(filename: str, versioned_path: str = "versions", delimiter: str = "--") -> None:
    """List all versions of the file.
    
    Args:
        filename: Name of the file to list versions for
        versioned_path: Directory containing the versions (default: "versions")
        delimiter: The delimiter used in version filenames (default: "--")
    """
    config = FileVersioningConfig(versioned_path=versioned_path, delimiter=delimiter)
    versioning = FileVersioning(config)
    versions = versioning.list_versions(filename)
    
    print(f"\nVersions for {filename} in {versioned_path}:")
    print("-" * 60)
    
    for version in versions:
        print(f"{version.filename:<40} {version.size:>8} bytes  "
              f"{version.timestamp.strftime('%Y-%m-%d %H:%M:%S')}  "
              f"{version.compression.value}")


def main():
    filename = "example.ini"
    
    # Create the example file
    create_example_file(filename)
    print(f"Created example file: {filename}")
    
    # Create default version
    default_version = create_default_version(filename)
    print(f"Created default version: {os.path.basename(default_version)}")
    
    # Create version in backups directory with custom delimiter
    backup_version = create_custom_backup_version(filename)
    print(f"Created backup version: {os.path.basename(backup_version)}")
    
    # Create compressed versions
    compressed_versions = create_compressed_versions(filename)
    for version in compressed_versions:
        print(f"Created compressed version: {os.path.basename(version)}")
    
    # Create version with current timestamp
    now_version = create_now_timestamp_version(filename)
    print(f"Created 'now' timestamp version: {os.path.basename(now_version)}")
    
    # List all versions from both directories
    list_all_versions(filename)  # List versions in default directory with default delimiter
    list_all_versions(filename, "backups", "__")  # List versions in backups directory with custom delimiter


if __name__ == "__main__":
    main()