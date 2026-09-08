# Task 3.4 — Apache Web Log 404 Parser

`parse_web_logs.py` downloads an Apache access log (Combined Log Format),
parses it with regular expressions, finds every entry that returned an
HTTP 404, extracts the client IP from those lines, deduplicates, and writes
the unique addresses — one per line — to `suspicious_ips.txt`.

That output file is the input to Tasks 3.5 and 3.6, which read it expecting
**one IP address per line and nothing else** — no header, no counts, no blank
lines. This tool produces exactly that.

## Requirements

- Python 3.6+ (standard library only — `re`, `urllib`, `argparse`).
- No third-party packages; `requirements.txt` is intentionally empty. Create a
  venv for consistency with the rest of the phase:

  ```bash
  python3 -m venv .venv
  source .venv/bin/activate
  # nothing to pip install; stdlib only
  ```

## Usage

```bash
./parse_web_logs.py [-u URL] [-o OUTPUT] [--status CODE]
```

| Flag              | Default                                   | Meaning                                  |
|-------------------|-------------------------------------------|------------------------------------------|
| `-u`, `--url`     | elastic/examples Apache sample log        | Log URL to download                      |
| `-o`, `--output`  | `suspicious_ips.txt`                       | Output file (one IP per line)            |
| `--status`        | `404`                                      | HTTP status code to select               |

Run with no arguments to reproduce the assigned task exactly:

```bash
./parse_web_logs.py
```

This downloads the dataset itself (no manual download), writes
`suspicious_ips.txt`, and prints a short summary to stderr:

```
Parsed log from https://raw.githubusercontent.com/.../apache_logs
HTTP 404 entries: 213
Unique client IPs -> suspicious_ips.txt: 90
```

## What it does, and how

- **Fetches its own data** over HTTPS with `urllib` — no wget/manual step.
- **Parses with `re`, not string splitting.** The Combined Log Format line is
  matched with one anchored regex that captures the leading client IP and the
  HTTP status that follows the quoted request. Matching the quoted request field
  explicitly means request strings containing spaces or quotes don't throw off
  field alignment the way `line.split()` would.
- **Selects 404s, extracts the IP, deduplicates** while preserving first-seen
  order, so runs are deterministic and the file diffs cleanly.
- **Reports what it couldn't do.** A failed download exits `2` with the reason;
  any line that doesn't match the log format is counted and reported to stderr
  rather than silently dropped; an empty result set is called out.

**Exit codes:** `0` success · `1` no matching entries, or some lines were
unparsable (output still written) · `2` fatal (download failed / cannot write).

## Verifying the output

The result was cross-checked against an independent method:

```bash
# same answer via awk on the raw log — 404 in field 9, unique field-1 IPs
awk '$9 == "404" {print $1}' apache_logs | sort -u | wc -l
```

On the assigned dataset this yields **90**, matching the script's output, and
every line of `suspicious_ips.txt` is a clean dotted-quad IPv4 address with no
duplicates or blank lines.
