# Task 3.7 — MITRE ATT&CK Groups Scraper

`scrape_mitre.py` fetches the MITRE ATT&CK Groups directory
(https://attack.mitre.org/groups/) with `requests`, parses the groups table with
`BeautifulSoup`, and stores the **ID**, **Name**, and **Associated Groups**
columns in a local SQLite database (`threat_intel.db`) as a typed table with a
primary key on the group ID — a schema you can hand to another program without
explanation.

## Requirements

Third-party packages (see `requirements.txt`):

- `requests` — HTTP fetch
- `beautifulsoup4` — HTML parsing
- `sqlite3` is part of the Python standard library (no install needed)

Set up in a virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Usage

```bash
./scrape_mitre.py [-u URL] [-d DBFILE] [--table TABLE] [--print]
```

| Flag             | Default                          | Meaning                                  |
|------------------|----------------------------------|------------------------------------------|
| `-u`, `--url`    | `https://attack.mitre.org/groups/` | Groups directory URL to scrape         |
| `-d`, `--db`     | `threat_intel.db`                 | SQLite database file to create/update    |
| `--table`        | `groups`                          | Table name                               |
| `--print`        | (off)                             | Print stored rows after inserting        |

Run with no arguments to reproduce the assigned task:

```bash
./scrape_mitre.py --print
```

This downloads the page, populates `threat_intel.db`, and prints each stored
group. A short summary goes to stderr:

```
Scraped 180 groups -> threat_intel.db (table: groups)
```

## Schema

```sql
CREATE TABLE IF NOT EXISTS groups (
    group_id           TEXT PRIMARY KEY,   -- e.g. G0018
    name               TEXT NOT NULL,      -- e.g. admin@338
    associated_groups  TEXT                -- comma-separated aliases, '' if none
);
```

- `group_id` is the primary key, so each ATT&CK group appears once and a re-scrape
  updates in place (`INSERT OR REPLACE`) rather than duplicating rows.
- `name` is `NOT NULL`.
- `associated_groups` holds the comma-separated alias list MITRE publishes, or an
  empty string when a group has none.

Query it like any SQLite DB:

```bash
sqlite3 threat_intel.db "SELECT group_id, name FROM groups WHERE associated_groups LIKE '%Fancy Bear%';"
```

## Design notes

- **Fetches its own data** — no manual download; `requests` with browser-like
  headers so MITRE serves the normal page.
- **Columns located by header name, not position.** The parser reads the table's
  header row and maps `ID` / `Name` / `Associated Groups` to indices, so if MITRE
  reorders columns the data still lands in the right place.
- **Fails loudly on structural change.** If no table with the expected headers is
  found, or zero rows parse, the tool prints a clear message and exits non-zero
  rather than writing an empty or garbage database.
- **Idempotent re-runs.** The primary key plus `INSERT OR REPLACE` means running
  it again refreshes the data without creating duplicates.

**Exit codes:** `0` success · `1` fetched but parsed zero rows (structure may have
changed) · `2` fatal (download failed, table not found, cannot write DB).

## Note on running location

Run this on the **Infra-Node**, which has the internet path. `threat_intel.db`
and the script live there under `05_Data_Operator/`; move the DB to the
workstation over SSH to commit it, per the phase standard.
