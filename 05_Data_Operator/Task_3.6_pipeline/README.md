# Task 3.9 — Threat-Intel Pipeline Orchestrator

`run_intel_pipeline.sh` chains the phase's collection tools into a single
command:

1. **Stage 1** — runs the Task 3.4 log parser (`parse_web_logs.py`), which
   downloads the Apache log and writes `suspicious_ips.txt`.
2. **Stage 2** — runs the Task 3.8 enricher (`enrich_ips.py`) against that file
   to print the final GeoIP report.

The pipeline **fails as a unit**: each stage's output is checked before the next
stage runs, and the orchestrator exits non-zero the moment a stage fails or
produces nothing. It never runs the enricher on an empty file and never reports
success after doing nothing.

## Requirements

- Bash, `python3`, and the two Python tools from Tasks 3.4 and 3.8.
- Those tools' own dependencies (the enricher/parser are stdlib-only; if a tool
  needs a venv, activate it first — see each tool's README).
- No third-party packages for the orchestrator itself.

## Usage

```bash
./run_intel_pipeline.sh [-u LOG_URL] [-o IP_FILE] [-d DELAY]
```

| Flag | Default                          | Meaning                                             |
|------|----------------------------------|-----------------------------------------------------|
| `-u` | (parser's built-in URL)          | Apache log URL passed to the parser                 |
| `-o` | `suspicious_ips.txt`             | Intermediate IP file between the two stages         |
| `-d` | `1.0`                            | Seconds between enricher lookups (rate limit)       |
| `-h` | —                                | Show help                                           |

Run with no arguments to execute the full default pipeline:

```bash
./run_intel_pipeline.sh
```

### Tool locations

By default the orchestrator finds the two tools relative to its own location in
the repo:

```
05_Data_Operator/
├── Task_3.4_web_log_parser/parse_web_logs.py
├── Task_3.8_ip_enrichment/enrich_ips.py
└── Task_3.9_pipeline/run_intel_pipeline.sh   <- this script
```

If your layout differs, point it at the tools with environment variables:

```bash
PARSER=/path/to/parse_web_logs.py ENRICHER=/path/to/enrich_ips.py ./run_intel_pipeline.sh
```

`PYTHON` can likewise override the interpreter (e.g. a venv's python).

## Fail-as-a-unit behavior

The whole point of the orchestrator is that it refuses to go quietly dead. Between
the two stages it checks three distinct "nothing" conditions, each a real way
automated collection dies silently:

| Condition | What it catches | Result |
|---|---|---|
| Parser exits non-zero | download failed, unparsable input | stop, exit 1, enricher never runs |
| `suspicious_ips.txt` not created | parser "succeeded" but wrote nothing | stop, exit 1, enricher never runs |
| `suspicious_ips.txt` is empty / no addresses | parser ran but found zero 404 IPs | stop, exit 1, enricher never runs |

It also **deletes any stale `suspicious_ips.txt` before Stage 1**, so a leftover
file from a previous run can never be mistaken for this run's output if the parser
fails.

Stage 2's own exit code is preserved: if the enricher runs but some individual
GeoIP lookups fail (it exits 1 for partial failure), the pipeline surfaces that
non-zero code rather than masking it — a partial report is reported as partial.

**Exit codes:** `0` both stages succeeded and a non-empty report was produced ·
`1` a stage failed or produced nothing for the next stage · `2` usage error /
prerequisites missing (a tool or `python3` not found).

## Verifying the failure handling

The failure paths were tested with stub tools simulating each mode — empty
output, non-zero exit, exit-0-but-no-file, and a stale leftover file. In every
failure case the pipeline exits non-zero and the enricher's report never prints.
A pipeline you have only ever watched succeed has untested failure handling; these
were exercised deliberately.

## Note on running location

Run on the **Infra-Node**, which has the internet path both stages need. The
script and its intermediate `suspicious_ips.txt` live under `05_Data_Operator/`;
move any outputs to the workstation over SSH to commit them.
