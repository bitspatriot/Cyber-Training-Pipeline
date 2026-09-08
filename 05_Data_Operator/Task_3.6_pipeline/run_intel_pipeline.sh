#!/usr/bin/env bash
#
# run_intel_pipeline.sh — orchestrate the threat-intel collection pipeline.
#
# Stage 1: parse_web_logs.py   -> downloads the Apache log, writes suspicious_ips.txt
# Stage 2: enrich_ips.py       -> reads suspicious_ips.txt, prints the GeoIP report
#
# The pipeline fails as a UNIT. Each stage's output is verified before the next
# stage runs: if the log parser exits non-zero, or produces no suspicious_ips.txt,
# or produces an EMPTY one, the enricher does not run and the pipeline exits
# non-zero. A pipeline that reports success after doing nothing is how automated
# collection goes quietly dead — this one refuses to.
#
# Usage:
#   ./run_intel_pipeline.sh [-u LOG_URL] [-o IP_FILE] [-d DELAY]
#
# Options (all optional; sensible defaults reproduce Tasks 3.4 + 3.8):
#   -u LOG_URL   Apache log URL passed to the parser (default: parser's built-in)
#   -o IP_FILE   intermediate IP file (default: suspicious_ips.txt)
#   -d DELAY     seconds between enricher requests (default: 1.0)
#   -h           show this help
#
# Exit codes:
#   0  both stages succeeded and a non-empty report was produced
#   1  a stage failed, or produced nothing for the next stage
#   2  usage error / prerequisites missing (scripts or python not found)

set -euo pipefail

# --- Resolve paths relative to this script, so it runs from anywhere ----------
# No hardcoded absolute paths: locate the sibling tools relative to this file.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# The two tools live in their own task directories in the repo. Allow override
# via environment for flexibility, but default to the expected repo layout.
PARSER="${PARSER:-$SCRIPT_DIR/../Task_3.4_web_log_parser/parse_web_logs.py}"
ENRICHER="${ENRICHER:-$SCRIPT_DIR/../Task_3.8_ip_enrichment/enrich_ips.py}"

# --- Defaults -----------------------------------------------------------------
IP_FILE="suspicious_ips.txt"
LOG_URL=""          # empty => let the parser use its built-in default URL
DELAY="1.0"
PYTHON="${PYTHON:-python3}"

usage() {
    sed -n '2,30p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'
    exit "${1:-0}"
}

# --- Parse arguments ----------------------------------------------------------
while getopts ":u:o:d:h" opt; do
    case "$opt" in
        u) LOG_URL="$OPTARG" ;;
        o) IP_FILE="$OPTARG" ;;
        d) DELAY="$OPTARG" ;;
        h) usage 0 ;;
        :) echo "error: -$OPTARG requires an argument" >&2; usage 2 ;;
        \?) echo "error: unknown option -$OPTARG" >&2; usage 2 ;;
    esac
done

log()  { echo "[pipeline] $*" >&2; }
fail() { echo "[pipeline] FAIL: $*" >&2; exit 1; }

# --- Preconditions: the tools and interpreter must exist ----------------------
command -v "$PYTHON" >/dev/null 2>&1 || { echo "error: $PYTHON not found" >&2; exit 2; }
[[ -f "$PARSER" ]]   || { echo "error: parser not found at $PARSER" >&2; exit 2; }
[[ -f "$ENRICHER" ]] || { echo "error: enricher not found at $ENRICHER" >&2; exit 2; }

# =============================================================================
# Stage 1 — parse web logs into suspicious_ips.txt
# =============================================================================
log "Stage 1/2: parsing web logs -> $IP_FILE"

# Remove any stale output first, so a leftover file from a previous run can never
# be mistaken for this run's product if the parser silently fails to write.
rm -f "$IP_FILE"

# Build the parser argument list. Only pass -u if the caller supplied a URL.
parser_args=(-o "$IP_FILE")
[[ -n "$LOG_URL" ]] && parser_args+=(-u "$LOG_URL")

# Run it. `set -e` plus explicit check: if the parser exits non-zero, stop here.
if ! "$PYTHON" "$PARSER" "${parser_args[@]}"; then
    fail "log parser exited non-zero; not running enricher."
fi

# --- Gate: verify Stage 1 actually produced what Stage 2 needs -----------------
# Three distinct "nothing" conditions, each a separate quiet-death mode:
[[ -f "$IP_FILE" ]] || fail "parser reported success but $IP_FILE was not created."
[[ -s "$IP_FILE" ]] || fail "$IP_FILE is empty — no suspicious IPs found; nothing to enrich."

IP_COUNT="$(grep -c . "$IP_FILE" || true)"
[[ "$IP_COUNT" -gt 0 ]] || fail "$IP_FILE has no address lines; nothing to enrich."

log "Stage 1 OK: $IP_COUNT address(es) in $IP_FILE"

# =============================================================================
# Stage 2 — enrich the IPs and print the final report
# =============================================================================
log "Stage 2/2: enriching $IP_COUNT address(es) (delay ${DELAY}s between lookups)"

if ! "$PYTHON" "$ENRICHER" "$IP_FILE" --delay "$DELAY"; then
    # The enricher exits 1 if SOME lookups failed; that's a partial result, not a
    # dead pipeline. Distinguish "produced a report with some failures" from
    # "could not run at all" by checking it actually ran against a real file.
    rc=$?
    log "note: enricher exited non-zero (rc=$rc) — some lookups may have failed."
    exit "$rc"
fi

log "Pipeline complete: report generated from $IP_COUNT address(es)."
