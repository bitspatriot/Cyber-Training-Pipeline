#!/usr/bin/env python3
"""
compare_hashes.py — diff two integrity_check.py CSVs into added/removed/modified.

A single hash CSV is only a baseline. This tool takes two of them (an earlier
"baseline" and a later "current") and reports what actually changed between the
runs: files added, files removed, and files whose SHA-256 differs.

Usage:
    ./compare_hashes.py <baseline.csv> <current.csv> [-o report.csv]

Examples:
    ./compare_hashes.py etc_baseline.csv etc_current.csv
    ./compare_hashes.py etc_baseline.csv etc_current.csv -o etc_changes.csv

Exit codes:
    0  the two baselines are identical (no changes)
    1  differences were found (added / removed / modified)
    2  usage / fatal error (e.g. a CSV is missing or malformed)
"""

import argparse
import csv
import os
import sys


def load_hashes(csv_path):
    """Load a File_Path,SHA256_Hash CSV into a dict {path: hash}.

    Raises SystemExit(2) with a clear message if the file is missing or does
    not have the expected header/columns.
    """
    if not os.path.isfile(csv_path):
        print(f"error: {csv_path!r} does not exist", file=sys.stderr)
        raise SystemExit(2)

    mapping = {}
    with open(csv_path, newline="") as handle:
        reader = csv.reader(handle)
        try:
            header = next(reader)
        except StopIteration:
            print(f"error: {csv_path!r} is empty", file=sys.stderr)
            raise SystemExit(2)

        if header != ["File_Path", "SHA256_Hash"]:
            print(
                f"error: {csv_path!r} has unexpected header {header!r}; "
                f"expected ['File_Path', 'SHA256_Hash']",
                file=sys.stderr,
            )
            raise SystemExit(2)

        for row in reader:
            if len(row) != 2:
                # Report the bad row rather than silently skipping it.
                print(f"warning: skipping malformed row in {csv_path!r}: {row!r}",
                      file=sys.stderr)
                continue
            path, digest = row
            mapping[path] = digest

    return mapping


def compare(baseline, current):
    """Return (added, removed, modified) from two {path: hash} dicts.

    added    - paths in current but not baseline
    removed  - paths in baseline but not current
    modified - paths in both whose hash changed; list of (path, old, new)
    """
    baseline_paths = set(baseline)
    current_paths = set(current)

    added = sorted(current_paths - baseline_paths)
    removed = sorted(baseline_paths - current_paths)
    modified = sorted(
        (path, baseline[path], current[path])
        for path in (baseline_paths & current_paths)
        if baseline[path] != current[path]
    )
    return added, removed, modified


def print_report(added, removed, modified):
    """Human-readable summary to stdout."""
    print("=== Integrity comparison ===")
    print(f"Added:    {len(added)}")
    print(f"Removed:  {len(removed)}")
    print(f"Modified: {len(modified)}")
    print()

    if added:
        print("--- ADDED (present now, absent in baseline) ---")
        for path in added:
            print(f"  + {path}")
        print()
    if removed:
        print("--- REMOVED (present in baseline, absent now) ---")
        for path in removed:
            print(f"  - {path}")
        print()
    if modified:
        print("--- MODIFIED (hash changed) ---")
        for path, old, new in modified:
            print(f"  ~ {path}")
            print(f"      was: {old}")
            print(f"      now: {new}")
        print()

    if not (added or removed or modified):
        print("No changes: the two baselines are identical.")


def write_report_csv(added, removed, modified, output_path):
    """Write a machine-readable change report: Status,File_Path,Old_Hash,New_Hash."""
    with open(output_path, "w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["Status", "File_Path", "Old_Hash", "New_Hash"])
        for path in added:
            writer.writerow(["ADDED", path, "", ""])
        for path in removed:
            writer.writerow(["REMOVED", path, "", ""])
        for path, old, new in modified:
            writer.writerow(["MODIFIED", path, old, new])


def parse_args(argv):
    parser = argparse.ArgumentParser(
        description="Compare two integrity_check.py CSVs and report what was "
                    "added, removed, and modified.",
    )
    parser.add_argument("baseline", help="Earlier CSV (the baseline).")
    parser.add_argument("current", help="Later CSV (the current state).")
    parser.add_argument(
        "-o", "--output",
        default=None,
        help="Optional CSV to write the change report to "
             "(Status,File_Path,Old_Hash,New_Hash).",
    )
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv if argv is not None else sys.argv[1:])

    baseline = load_hashes(args.baseline)
    current = load_hashes(args.current)

    added, removed, modified = compare(baseline, current)
    print_report(added, removed, modified)

    if args.output:
        write_report_csv(added, removed, modified, args.output)
        print(f"Change report written -> {args.output}", file=sys.stderr)

    return 1 if (added or removed or modified) else 0


if __name__ == "__main__":
    sys.exit(main())
