#!/usr/bin/env python3
"""
enrich_ips.py — enrich suspicious IPs with GeoIP country and ISP data.

Reads a file of IP addresses (one per line, as produced by parse_web_logs.py),
queries the free no-auth GeoIP service at http://ip-api.com/json/<IP> for each,
and prints a report of IP, country, and ISP. A 1-second pause between requests
keeps the tool under ip-api.com's free-tier rate limit.

Per-IP failures (lookup "fail" status, HTTP errors, timeouts, malformed JSON)
are reported inline and do not stop the run — one bad address never hides the
rest of the report.

Usage:
    ./enrich_ips.py [INPUT] [--delay SECONDS] [--csv OUTPUT.csv]

Defaults reproduce the assigned task:
    INPUT = suspicious_ips.txt
    delay = 1.0 second between requests

Examples:
    ./enrich_ips.py
    ./enrich_ips.py suspicious_ips.txt
    ./enrich_ips.py suspicious_ips.txt --delay 1.5 --csv enriched.csv

Exit codes:
    0  all addresses enriched successfully
    1  completed, but one or more lookups failed (see the report)
    2  usage / fatal error (input file missing/empty)

SECURITY NOTE — ip-api.com's free tier is HTTP only (cleartext). The *response*
is public data, but the *queries* reveal which addresses this analyst found
interesting and in what order, on the wire, to any observer. Where that mattered
(real investigation, sensitive infrastructure) you would use an HTTPS-capable or
paid endpoint, tunnel the lookups (e.g. through the SSH bastion / a VPN), batch
via ip-api's HTTPS "pro" API, or run against a local MaxMind GeoLite2 database so
no query leaves the host at all. See README for detail.
"""

import argparse
import csv
import json
import sys
import time
import urllib.request
import urllib.error

API_URL = "http://ip-api.com/json/{ip}"
DEFAULT_INPUT = "suspicious_ips.txt"
DEFAULT_DELAY = 1.0


def read_ips(path):
    """Read non-empty, stripped lines from the input file.

    Exits 2 with a clear message if the file is missing or has no addresses.
    """
    try:
        with open(path) as handle:
            ips = [line.strip() for line in handle if line.strip()]
    except FileNotFoundError:
        print(f"error: input file {path!r} not found", file=sys.stderr)
        raise SystemExit(2)
    except OSError as exc:
        print(f"error: cannot read {path!r} — {exc}", file=sys.stderr)
        raise SystemExit(2)

    if not ips:
        print(f"error: {path!r} contains no addresses", file=sys.stderr)
        raise SystemExit(2)
    return ips


def lookup(ip, timeout=15):
    """Query the GeoIP API for one IP.

    Returns a dict:
        {"ip", "country", "isp", "ok": True}                      on success
        {"ip", "error": "<reason>", "ok": False}                  on any failure

    Never raises for network/API problems — a failed lookup is data to report,
    not a crash. Only programming errors would propagate.
    """
    url = API_URL.format(ip=ip)
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            payload = resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        return {"ip": ip, "error": f"HTTP {exc.code}", "ok": False}
    except urllib.error.URLError as exc:
        return {"ip": ip, "error": f"unreachable: {exc.reason}", "ok": False}
    except (OSError, TimeoutError) as exc:
        return {"ip": ip, "error": f"network error: {exc}", "ok": False}

    try:
        data = json.loads(payload)
    except json.JSONDecodeError:
        return {"ip": ip, "error": "malformed JSON response", "ok": False}

    # ip-api.com signals per-query outcome in the "status" field.
    if data.get("status") != "success":
        reason = data.get("message", "lookup failed")
        return {"ip": ip, "error": reason, "ok": False}

    return {
        "ip": ip,
        "country": data.get("country", "") or "",
        "isp": data.get("isp", "") or "",
        "ok": True,
    }


def print_header():
    print(f"{'IP ADDRESS':<16}  {'COUNTRY':<24}  ISP")
    print(f"{'-'*16}  {'-'*24}  {'-'*30}")


def print_row(result):
    if result["ok"]:
        print(f"{result['ip']:<16}  {result['country']:<24}  {result['isp']}")
    else:
        print(f"{result['ip']:<16}  {'(lookup failed)':<24}  {result['error']}")


def parse_args(argv):
    parser = argparse.ArgumentParser(
        description="Enrich a list of IPs with GeoIP country and ISP via ip-api.com.",
    )
    parser.add_argument("input", nargs="?", default=DEFAULT_INPUT,
                        help=f"File of IPs, one per line (default: {DEFAULT_INPUT}).")
    parser.add_argument("--delay", type=float, default=DEFAULT_DELAY,
                        help=f"Seconds to sleep between requests "
                             f"(default: {DEFAULT_DELAY}; keeps under the free-tier limit).")
    parser.add_argument("--csv", default=None,
                        help="Optional CSV to also write the report to "
                             "(IP,Country,ISP,Status).")
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv if argv is not None else sys.argv[1:])
    ips = read_ips(args.input)

    print_header()
    results = []
    failures = 0

    for i, ip in enumerate(ips):
        result = lookup(ip)
        results.append(result)
        if not result["ok"]:
            failures += 1
        print_row(result)

        # Rate-limit: sleep BETWEEN requests, not after the last one.
        if i < len(ips) - 1:
            time.sleep(args.delay)

    if args.csv:
        try:
            with open(args.csv, "w", newline="") as handle:
                writer = csv.writer(handle)
                writer.writerow(["IP", "Country", "ISP", "Status"])
                for r in results:
                    if r["ok"]:
                        writer.writerow([r["ip"], r["country"], r["isp"], "success"])
                    else:
                        writer.writerow([r["ip"], "", "", f"fail: {r['error']}"])
            print(f"\nReport also written -> {args.csv}", file=sys.stderr)
        except OSError as exc:
            print(f"warning: could not write {args.csv!r} — {exc}", file=sys.stderr)

    print(f"\nEnriched {len(ips)} address(es); {failures} lookup(s) failed.",
          file=sys.stderr)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
