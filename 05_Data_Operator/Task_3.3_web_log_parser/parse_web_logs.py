#!/usr/bin/env python3
"""
parse_web_logs.py — find client IPs that triggered HTTP 404s in an Apache log.

Downloads an Apache access log in Combined Log Format, parses each line with a
regular expression (not string splitting), selects the entries whose HTTP status
is 404, extracts the client IP from those lines, deduplicates, and writes one IP
per line to an output file. That output is consumed verbatim by later tasks, so
the file contains addresses and nothing else — no headers, counts, or blank lines.

Usage:
    ./parse_web_logs.py [-u URL] [-o OUTPUT] [--status CODE]

Defaults reproduce the assigned task:
    URL    = the elastic/examples Apache sample log
    OUTPUT = suspicious_ips.txt
    status = 404

Examples:
    ./parse_web_logs.py
    ./parse_web_logs.py -o suspicious_ips.txt
    ./parse_web_logs.py -u https://host/access.log --status 404 -o out.txt

Exit codes:
    0  success (log fetched, parsed, output written)
    1  no matching entries found (output written empty) OR some lines unparsable
    2  usage / fatal error (download failed, cannot write output)
"""

import argparse
import re
import sys
import urllib.request
import urllib.error

DEFAULT_URL = (
    "https://raw.githubusercontent.com/elastic/examples/master/"
    "Common%20Data%20Formats/apache_logs/apache_logs"
)
DEFAULT_OUTPUT = "suspicious_ips.txt"
DEFAULT_STATUS = "404"

# Combined Log Format, e.g.:
#   83.149.9.216 - - [17/May/2015:10:05:03 +0000] "GET /path HTTP/1.1" 200 203023 "ref" "agent"
#
# We capture the leading client IP and the numeric HTTP status that follows the
# quoted request. The request string can contain quotes/spaces, so we match a
# quoted field non-greedily, then the status code as the first number after it.
LOG_LINE_RE = re.compile(
    r'^(?P<ip>\d{1,3}(?:\.\d{1,3}){3})'   # client IP at start of line
    r'\s+\S+\s+\S+'                        # identd and userid (usually - -)
    r'\s+\[[^\]]+\]'                       # [timestamp]
    r'\s+"[^"]*"'                          # "request line"
    r'\s+(?P<status>\d{3})'                # HTTP status code
)


def fetch_log(url):
    """Download the log and return it as text.

    Raises SystemExit(2) with a clear message if the download fails, so the
    tool reports why it could not do its job instead of dying on a traceback.
    """
    try:
        with urllib.request.urlopen(url, timeout=30) as response:
            raw = response.read()
    except urllib.error.HTTPError as exc:
        print(f"error: download failed — HTTP {exc.code} for {url}", file=sys.stderr)
        raise SystemExit(2)
    except urllib.error.URLError as exc:
        print(f"error: could not reach {url} — {exc.reason}", file=sys.stderr)
        raise SystemExit(2)
    except OSError as exc:
        print(f"error: download failed — {exc}", file=sys.stderr)
        raise SystemExit(2)

    # Apache logs are effectively latin-1/utf-8; decode leniently so one odd
    # byte in a user agent doesn't abort the whole parse.
    return raw.decode("utf-8", errors="replace")


def extract_ips_by_status(log_text, wanted_status):
    """Parse log text; return (ordered_unique_ips, matched_count, unparsed_count).

    Deduplicates while preserving first-seen order (deterministic output).
    Lines that don't match the log pattern are counted and reported rather
    than silently ignored — an unparsable line is a fact worth surfacing.
    """
    seen = set()
    ordered = []
    matched = 0
    unparsed = 0

    for line in log_text.splitlines():
        if not line.strip():
            continue
        m = LOG_LINE_RE.match(line)
        if not m:
            unparsed += 1
            continue
        if m.group("status") == wanted_status:
            matched += 1
            ip = m.group("ip")
            if ip not in seen:
                seen.add(ip)
                ordered.append(ip)

    return ordered, matched, unparsed


def write_ips(ips, output_path):
    """Write one IP per line, nothing else. Trailing newline after the last IP."""
    try:
        with open(output_path, "w") as handle:
            for ip in ips:
                handle.write(f"{ip}\n")
    except OSError as exc:
        print(f"error: cannot write {output_path!r} — {exc}", file=sys.stderr)
        raise SystemExit(2)


def parse_args(argv):
    parser = argparse.ArgumentParser(
        description="Extract deduplicated client IPs that triggered a given HTTP "
                    "status (default 404) from an Apache Combined Log Format log.",
    )
    parser.add_argument("-u", "--url", default=DEFAULT_URL,
                        help="URL of the access log to download "
                             "(default: the elastic/examples Apache sample).")
    parser.add_argument("-o", "--output", default=DEFAULT_OUTPUT,
                        help=f"Output file, one IP per line (default: {DEFAULT_OUTPUT}).")
    parser.add_argument("--status", default=DEFAULT_STATUS,
                        help=f"HTTP status code to select (default: {DEFAULT_STATUS}).")
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv if argv is not None else sys.argv[1:])

    log_text = fetch_log(args.url)
    ips, matched, unparsed = extract_ips_by_status(log_text, args.status)
    write_ips(ips, args.output)

    print(f"Parsed log from {args.url}", file=sys.stderr)
    print(f"HTTP {args.status} entries: {matched}", file=sys.stderr)
    print(f"Unique client IPs -> {args.output}: {len(ips)}", file=sys.stderr)
    if unparsed:
        print(f"warning: {unparsed} line(s) did not match the log format and were skipped",
              file=sys.stderr)

    if not ips:
        print(f"warning: no HTTP {args.status} entries found; {args.output} is empty",
              file=sys.stderr)
        return 1
    if unparsed:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
