#!/usr/bin/env python3

"""File Versioning CLI tool.

This module provides a command-line interface for the py-file-versioning library,
allowing users to create, restore, list, and remove file versions with optional
compression and other configuration options.
"""

import argparse
import sys
from pathlib import Path

from py_file_versioning import CompressionType, FileVersioning, FileVersioningConfig, TimestampSource, TimezoneFormat, VersionError


def list_versions(file_path: str, config: FileVersioningConfig) -> None:
    """List all versions of a file with their details.

    Args:
        file_path: Path to the file to list versions for
        config: Configuration object for versioning
    """
    versioning = FileVersioning(config)
    base_path = Path(file_path)

    if not base_path.exists():
        print(f"Error: File {file_path} does not exist")
        return

    # Get all versions using FileVersioning's public method
    versions = versioning.list_versions(file_path)

    if not versions:
        print(f"No versions found for {file_path}")
        return

    print(f"\nVersions for {file_path}:")
    print("-" * 60)
    for version in versions:
        print(f"{version.filename:<40} {version.size:>8} bytes  {version.timestamp.strftime('%Y-%m-%d %H:%M:%S')}")


def main(args=None):
    """Main entry point for the CLI.

    Args:
        args: List of arguments (if None, sys.argv[1:] is used)
    """
    parser = argparse.ArgumentParser(
        description=f"{FileVersioning.LIB_NAME.replace('-', '')}: a flexible file versioning system with compression support"
    )
    parser.add_argument("-V", "--version", action="store_true", help="Show version information")
    parser.add_argument("command", nargs="?", choices=["create", "restore", "list", "remove"], help="Command to execute")
    parser.add_argument("file", nargs="?", help="File to version/restore/list")
    parser.add_argument("-t", "--target", help="Target path for restore")
    parser.add_argument("-d", "--versions-dir", default="versions", help="Directory to store versions (default: versions)")
    parser.add_argument(
        "-c",
        "--compression",
        choices=["none", "gzip", "bz2", "xz"],
        default="none",
        help="Compression type to use",
    )
    parser.add_argument("-m", "--max-versions", type=int, default=None, help="Maximum number of versions to keep")
    parser.add_argument(
        "--timestamp-source",
        choices=["modified", "now"],
        default="modified",
        help="Source for timestamps (modified time or current time)",
    )

    args = parser.parse_args(args)

    if args.version:
        print(f"{FileVersioning.LIB_NAME.replace('-', '')} v{FileVersioning.LIB_VERSION}")
        print(f"{FileVersioning.LIB_URL}")
        sys.exit(0)

    if not args.command:
        parser.error("command is required")

    if not args.file:
        parser.error("file is required")

    # Create configuration
    config = FileVersioningConfig(
        versioned_path=args.versions_dir,
        compression=CompressionType(args.compression),
        timezone_format=TimezoneFormat.LOCAL,
        max_count=args.max_versions,
        timestamp_format=(TimestampSource.NOW if args.timestamp_source == "now" else TimestampSource.MODIFIED),
    )

    # Initialize versioning
    versioning = FileVersioning(config)

    try:
        if args.command == "create":
            version_path = versioning.create_version(args.file)
            print(f"Created version: {version_path}")

        elif args.command == "restore":
            if not args.target:
                print("Error: --target required for restore command")
                sys.exit(1)
            versioning.restore_version(args.file, args.target)
            print(f"Restored {args.file} to {args.target}")

        elif args.command == "remove":
            versioning.remove_version(args.file)
            print(f"Removed version: {args.file}")

        elif args.command == "list":
            list_versions(args.file, config)

    except VersionError as e:
        print(f"Error: {str(e)}", file=sys.stderr)
        sys.exit(1)
    except FileNotFoundError as e:
        print(f"Error: {str(e)}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error: {str(e)}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
