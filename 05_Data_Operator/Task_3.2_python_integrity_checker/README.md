# Task 3.2 — Filesystem Integrity Check

Two command-line tools for baseline-and-compare integrity checking of a directory
tree. `integrity_check.py` hashes every readable file under a directory into a CSV;
`compare_hashes.py` diffs two such CSVs into a list of what was added, removed, and
modified. Built for `/etc` on the Infra-Node, but the path is an argument — they
work on any directory.

## Requirements

- Python 3.6+ (standard library only — `hashlib`, `csv`, `os`, `argparse`).
- No third-party packages, so `requirements.txt` is intentionally empty. A `venv`
  is still used for consistency with the rest of the phase:

  ```bash
  python3 -m venv .venv
  source .venv/bin/activate
  # nothing to pip install; stdlib only
  ```

## `integrity_check.py` — build a baseline

Recursively walks a directory, computes the SHA-256 of every **readable regular
file**, and writes a CSV with columns `File_Path,SHA256_Hash`.

```bash
./integrity_check.py <directory> [-o OUTPUT.csv] [--errors ERRORS.txt]
```

| Argument            | Meaning                                                              |
|---------------------|---------------------------------------------------------------------|
| `<directory>`       | Directory to walk (required, positional). e.g. `/etc`               |
| `-o`, `--output`    | CSV to write (default: `etc_hashes.csv`)                            |
| `--errors`          | Optional file for the full list of unreadable/skipped files         |

**Run it unprivileged.** Parts of `/etc` are not readable by a normal user. This
is deliberate: running as root would hash everything and hide the gaps. Instead,
files that cannot be opened are **left out of the CSV and reported separately**, so
a file missing due to permissions is never confused with a file that was deleted.

```bash
# baseline of /etc, capturing the unreadable list
./integrity_check.py /etc -o etc_baseline.csv --errors etc_unreadable.txt
```

Unreadable and skipped files are always printed to stderr; `--errors` also writes
them to a file. Symlinks and non-regular files (sockets, devices) are skipped and
reported rather than hashed.

**Exit codes:** `0` all files readable · `1` completed but some files unreadable
(output is incomplete — check the error report) · `2` usage error / not a directory.

## `compare_hashes.py` — turn two baselines into an integrity check

A single CSV is a baseline, not a check. Take a second baseline after some time (or
after a suspected change) and compare:

```bash
./compare_hashes.py <baseline.csv> <current.csv> [-o report.csv]
```

Reports three categories to stdout:
- **ADDED** — path present in `current` but not `baseline`
- **REMOVED** — path present in `baseline` but not `current`
- **MODIFIED** — path in both, but the SHA-256 differs (shows old and new hash)

With `-o`, also writes a machine-readable `Status,File_Path,Old_Hash,New_Hash` CSV.

**Exit codes:** `0` identical (no changes) · `1` differences found · `2` usage error
/ malformed or missing CSV.

## End-to-end workflow (as run on the Infra-Node against /etc)

```bash
# 1. First baseline
./integrity_check.py /etc -o etc_baseline.csv --errors etc_unreadable_baseline.txt

# 2. Change something under /etc (as root, deliberately, to exercise the check):
#    - modify a file:   echo "# test" | sudo tee -a /etc/hosts
#    - add a file:      echo "test"   | sudo tee /etc/integrity_test_file
#    - remove a file:   sudo rm /etc/integrity_test_file   (after a run that saw it)

# 3. Second run
./integrity_check.py /etc -o etc_current.csv --errors etc_unreadable_current.txt

# 4. Compare
./compare_hashes.py etc_baseline.csv etc_current.csv -o etc_changes.csv
```

Step 4's output is the actual integrity report: the exact set of files that changed
between the two runs, with the modifications you introduced showing up as ADDED /
REMOVED / MODIFIED.

## Design notes

- **Input is an argument, not an edited constant** — the directory, output path, and
  error file are all CLI flags.
- **Reports what it could not do** — unreadable files, unwalkable directories,
  skipped symlinks, and malformed CSV rows are all surfaced, never swallowed.
- **Deterministic output** — rows are sorted by path, so two runs of an unchanged
  tree produce byte-identical CSVs and the diff is clean.
- **Streamed hashing** — files are read in 64 KiB chunks, so large files don't have
  to fit in memory.
