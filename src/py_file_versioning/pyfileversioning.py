#!/usr/bin/env python3

"""File Versioning CLI tool.

This module provides a command-line interface for the py-file-versioning library,
allowing users to create, restore, list, and remove file versions with optional
compression and other configuration options.

Environment Variables:
    PFV_VERSIONS_PATH: Override default versions directory
    PFV_COMPRESSION: Override default compression type
"""

import argparse
import glob
import os
import sys
from pathlib import Path
from typing import List, Optional

from texttable import Texttable

from py_file_versioning import FileVersioning, FileVersioningConfig


def list_versions(file_path: Path, config: FileVersioningConfig) -> None:
    """List all versions of a file with their details.

    Args:
        file_path: Path to the file to list versions for
        config: Configuration object for versioning
    """
    versioning = FileVersioning(config)

    if not file_path.exists():
        print(f"Error: File {file_path} does not exist")
        return

    versions = versioning.list_versions(file_path)

    if not versions:
        print(f"No versions found for {file_path}")
        return

    print()
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


def create_parser() -> argparse.ArgumentParser:
    """Create and configure the argument parser.

    Returns:
        Configured argument parser with all CLI options
    """
    parser = argparse.ArgumentParser(description="py-file-versioning: A flexible file versioning system with compression support")
    parser.add_argument("-V", "--version", action="store_true", help="Show version information")
    parser.add_argument("command", nargs="?", choices=["create", "restore", "list", "remove"], help="Command to execute")
    parser.add_argument("files", nargs="*", help="One or more files to version/restore/list")
    parser.add_argument("-t", "--target", help="Target file path for restore (required for restore command)")
    parser.add_argument(
        "-d",
        "--versions-path",
        default=os.environ.get("PFV_VERSIONS_PATH", "versions"),
        help="Directory to store versions (default: versions, overridden by PFV_VERSIONS_PATH env var)",
    )
    parser.add_argument(
        "-c",
        "--compression",
        choices=["none", "gz", "bz2", "xz"],
        default=os.environ.get("PFV_COMPRESSION", "none"),
        help="Compression type to use (default: none, overridden by PFV_COMPRESSION env var)",
    )
    parser.add_argument("-m", "--max-versions", type=int, default=None, help="Maximum number of versions to keep")
    parser.add_argument(
        "-s", "--src", choices=["mod", "sto"], default="mod", help="Source for timestamps (mod: file modified time, sto: current time)"
    )
    parser.add_argument("-u", "--utc", action="store_true", help="Use UTC timezone for timestamps (default: local time)")
    parser.add_argument(
        "-D",
        "--delimiter",
        type=str,
        default=os.environ.get("PFV_DELIMITER", "--"),
        help="The delimiter to use (default: --, overridden by PFV_DELIMITER env var)",
    )
    return parser


def parse_args(args: Optional[List[str]] = None) -> argparse.Namespace:
    """Parse command line arguments.

    Args:
        args: List of arguments (if None, sys.argv[1:] is used)

    Returns:
        Parsed command line arguments
    """
    parser = create_parser()
    return parser.parse_args(args)


def expand_file_patterns(patterns: List[str]) -> List[Path]:
    """Expand file patterns into a list of paths.

    Args:
        patterns: List of file patterns to expand

    Returns:
        List of Path objects for matching files

    Raises:
        SystemExit: If no files match the patterns
    """
    expanded_files = []
    for pattern in patterns:
        # Normalize path separators for cross-platform compatibility
        normalized_pattern = os.path.normpath(pattern).replace("\\", "/")
        matches = glob.glob(normalized_pattern)

        if matches:
            expanded_files.extend(Path(match) for match in matches)
        else:
            expanded_files.append(Path(pattern))

    if not expanded_files:
        print("Error: No files match the specified patterns", file=sys.stderr)
        sys.exit(1)

    return expanded_files


def main(args: Optional[List[str]] = None) -> None:
    """Main entry point for the CLI.

    Args:
        args: List of arguments (if None, sys.argv[1:] is used)
    """
    args = parse_args(args)

    if args.version:
        print(f"{FileVersioning.LIB_NAME} v{FileVersioning.LIB_VERSION}")
        print(f"{FileVersioning.LIB_URL}")
        sys.exit(0)

    if not args.command:
        parser = create_parser()
        parser.error("command is required")

    # Create configuration
    config = FileVersioningConfig(
        compression=args.compression,
        use_utc=args.utc,
        max_versions=args.max_versions,
        use_modified_time=(args.src != "sto"),
        versions_path=args.versions_path,
        delimiter=args.delimiter,
    )

    # Initialize versioning
    versioning = FileVersioning(config)

    try:
        if args.command == "restore" and not args.target:
            print("Error: --target required for restore command")
            sys.exit(1)

        expanded_files = expand_file_patterns(args.files)
        error_count = 0

        for file_path in expanded_files:
            try:
                if args.command == "create":
                    version_path, removed_count, error_msg = versioning.create_version(file_path)
                    print(f"Created version: {version_path}")
                    if removed_count:
                        print(f"Removed {removed_count} version(s)")
                    elif error_msg:
                        print(f"Warning: {error_msg}")

                elif args.command == "restore":
                    versioning.restore_version(file_path, args.target)
                    print(f"Restored {file_path} to {args.target}")

                elif args.command == "remove":
                    versioning.remove_version(file_path)
                    print(f"Removed version: {file_path}")

                elif args.command == "list":
                    list_versions(file_path, config)

            except FileNotFoundError as e:
                print(f"Error processing {file_path}: {e}", file=sys.stderr)
                error_count += 1
            except Exception as e:
                print(f"Error processing {file_path}: {e}", file=sys.stderr)
                error_count += 1

        if error_count > 0:
            sys.exit(1)

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
