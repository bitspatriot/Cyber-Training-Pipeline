# Task 3.8 — GeoIP Enrichment of Suspicious IPs

`enrich_ips.py` reads the suspicious IP list from Task 3.4
(`suspicious_ips.txt`, one address per line) and, for each address, queries the
free no-auth GeoIP service at `http://ip-api.com/json/<IP>`. It prints a report
of **IP address, country, and ISP**, rate-limiting itself with a 1-second pause
between requests to stay under the free tier's limit.

## Requirements

- Python 3.6+ (standard library only — `urllib`, `json`, `csv`, `time`,
  `argparse`). `requirements.txt` is intentionally empty. Use a venv for phase
  consistency:

  ```bash
  python3 -m venv .venv
  source .venv/bin/activate
  # nothing to pip install; stdlib only
  ```

## Usage

```bash
./enrich_ips.py [INPUT] [--delay SECONDS] [--csv OUTPUT.csv]
```

| Argument / flag  | Default              | Meaning                                        |
|------------------|----------------------|------------------------------------------------|
| `INPUT`          | `suspicious_ips.txt` | File of IPs, one per line (positional, optional)|
| `--delay`        | `1.0`                | Seconds to sleep between requests               |
| `--csv`          | (none)               | Also write the report to a CSV                  |

Run with no arguments to reproduce the assigned task (reads `suspicious_ips.txt`,
1-second delay):

```bash
./enrich_ips.py
```

Output is a console table:

```
IP ADDRESS        COUNTRY                   ISP
----------------  ------------------------  ------------------------------
66.249.73.185     United States             Google LLC
208.91.156.11     Netherlands               Example Telecom BV
...
```

A per-IP lookup that fails (reserved range, invalid address, API error, timeout)
is shown inline as `(lookup failed)` with the reason, and the run continues — one
bad address never suppresses the rest of the report. A summary and any failure
count go to stderr.

**Exit codes:** `0` all addresses enriched · `1` completed but ≥1 lookup failed
· `2` fatal (input file missing/empty).

## Rate limiting

The free `ip-api.com` tier throttles clients that exceed ~45 requests/minute. The
`--delay` (default 1.0s) sleeps **between** requests — applied to the gaps, not
after the final lookup — so a list of N addresses takes about N−1 seconds of
pause. If you still get throttled (HTTP 429 / `status: fail` with a rate message),
raise `--delay`.

## Security note — the query is the sensitive part, not the response

`ip-api.com`'s free tier is **HTTP only (cleartext)**. This is worth thinking
about precisely because the naive reaction ("it's only public GeoIP data, who
cares if it's plaintext") misses the real exposure:

- The **response** is public reference data — country and ISP for an address
  anyone can look up. An observer learns nothing new from it.
- The **query** is the tell. On the wire, in cleartext, each request reveals
  *which* addresses this analyst flagged as suspicious, in what order, and when —
  i.e. the shape and timing of an active investigation. To anyone monitoring the
  network path (an ISP, a compromised gateway, an adversary with a tap), that
  metadata is intelligence about what you know and what you're chasing.

Where that mattered, the alternatives, roughly in order of preference:

1. **Query a local GeoIP database** (MaxMind GeoLite2) so no lookup leaves the
   host at all — the strongest option: zero query metadata on the wire.
2. **Use an HTTPS endpoint** — ip-api.com's paid/pro API offers TLS, which hides
   the query contents (though not that you're talking to a GeoIP service).
3. **Tunnel the lookups** through the SSH bastion or a VPN so the queries don't
   traverse the local/enterprise network in the clear.
4. **Batch** the lookups (ip-api's batch endpoint) to reduce the timing signal.

For this lab against public sample data the cleartext free tier is fine; the point
is recognizing *why* it wouldn't be in a real engagement.

## Note on running location

Run on the **Infra-Node**, which has the internet path. The script, its input
`suspicious_ips.txt`, and any CSV output live there under `05_Data_Operator/`;
move outputs to the workstation over SSH to commit them.
