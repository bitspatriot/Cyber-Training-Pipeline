#!/usr/bin/env python3
"""
integrity_check.py — recursively hash every readable file under a directory.

Walks a directory tree, computes the SHA-256 of each readable file, and writes
a two-column CSV (File_Path, SHA256_Hash). Files that cannot be opened (almost
always a permissions problem when run unprivileged) are NOT silently dropped:
each one is reported to stderr and, optionally, to a separate errors file, so a
file missing from the output because you couldn't read it is never mistaken for
a file that was deleted.

Usage:
    ./integrity_check.py <directory> [-o OUTPUT.csv] [--errors ERRORS.txt]

Examples:
    ./integrity_check.py /etc -o etc_hashes.csv
    ./integrity_check.py /etc -o etc_baseline.csv --errors etc_unreadable.txt

Exit codes:
    0  completed, every file readable
    1  completed, but one or more files could not be read (see the error report)
    2  usage / fatal error (e.g. the path is not a directory)
"""

import argparse
import csv
import hashlib
import os
import sys

# Read files in chunks so a large file never has to sit in memory all at once.
CHUNK_SIZE = 65536  # 64 KiB


def sha256_of_file(path):
    """Return the hex SHA-256 of the file at `path`.

    Raises OSError (PermissionError, FileNotFoundError, etc.) if the file
    cannot be opened or read; the caller decides how to report it.
    """
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(CHUNK_SIZE), b""):
            digest.update(chunk)
    return digest.hexdigest()


def walk_and_hash(root):
    """Walk `root` and hash every regular file.

    Returns a tuple (results, errors) where:
      results is a sorted list of (file_path, sha256_hex)
      errors  is a sorted list of (file_path, reason) for files that could
              not be opened, read, or walked into.
    """
    results = []
    errors = []

    # onerror is called when os.walk itself cannot descend into a directory
    # (e.g. an unreadable subdirectory). Without this, walk silently skips it,
    # which is exactly the kind of invisible gap this tool exists to surface.
    def on_walk_error(err):
        errors.append((getattr(err, "filename", str(err)), f"walk error: {err.strerror or err}"))

    for dirpath, _dirnames, filenames in os.walk(root, onerror=on_walk_error):
        for name in filenames:
            full_path = os.path.join(dirpath, name)

            # Skip symlinks: hashing the target duplicates content and can loop
            # or wander outside the tree. Record them so they aren't silently
            # absent, but don't hash them.
            if os.path.islink(full_path):
                errors.append((full_path, "skipped: symbolic link"))
                continue

            # Only hash regular files. Sockets, devices, and fifos under /etc
            # are rare but real, and open()ing them is meaningless or hangs.
            if not os.path.isfile(full_path):
                errors.append((full_path, "skipped: not a regular file"))
                continue

            try:
                results.append((full_path, sha256_of_file(full_path)))
            except OSError as exc:
                # PermissionError, FileNotFoundError (races), IsADirectoryError...
                reason = exc.strerror or exc.__class__.__name__
                errors.append((full_path, f"unreadable: {reason}"))

    results.sort()
    errors.sort()
    return results, errors


def write_csv(results, output_path):
    """Write the (File_Path, SHA256_Hash) rows to a CSV with a header."""
    with open(output_path, "w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["File_Path", "SHA256_Hash"])
        writer.writerows(results)


def write_errors(errors, errors_path):
    """Write the list of unreadable/skipped files to a plain-text report."""
    with open(errors_path, "w") as handle:
        for path, reason in errors:
            handle.write(f"{path}\t{reason}\n")


def parse_args(argv):
    parser = argparse.ArgumentParser(
        description="Recursively SHA-256 every readable file under a directory "
                    "and write a File_Path,SHA256_Hash CSV.",
    )
    parser.add_argument(
        "directory",
        help="Directory to walk (e.g. /etc). Required.",
    )
    parser.add_argument(
        "-o", "--output",
        default="etc_hashes.csv",
        help="CSV file to write (default: etc_hashes.csv).",
    )
    parser.add_argument(
        "--errors",
        default=None,
        help="Optional file to write the list of unreadable/skipped files to. "
             "Unreadable files are always reported to stderr regardless.",
    )
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv if argv is not None else sys.argv[1:])

    if not os.path.isdir(args.directory):
        print(f"error: {args.directory!r} is not a directory", file=sys.stderr)
        return 2

    results, errors = walk_and_hash(args.directory)

    write_csv(results, args.output)
    print(f"Hashed {len(results)} files -> {args.output}", file=sys.stderr)

    if errors:
        print(f"Could not read {len(errors)} entries:", file=sys.stderr)
        for path, reason in errors:
            print(f"  {path}: {reason}", file=sys.stderr)
        if args.errors:
            write_errors(errors, args.errors)
            print(f"Full unreadable list -> {args.errors}", file=sys.stderr)
        # Non-zero exit so an automated caller knows the output is incomplete.
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
