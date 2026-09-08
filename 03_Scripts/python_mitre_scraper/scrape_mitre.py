#!/usr/bin/env python3
"""
scrape_mitre.py — build a local SQLite copy of the MITRE ATT&CK Groups directory.

Fetches the ATT&CK Groups index (https://attack.mitre.org/groups/) with requests,
parses the groups table with BeautifulSoup, and stores the ID, Name, and
Associated Groups columns in a typed SQLite table (threat_intel.db).

The parser identifies columns by their header text rather than by fixed position,
so a reordered column doesn't silently corrupt the data, and it fails loudly if
the expected columns are missing rather than inserting garbage.

Usage:
    ./scrape_mitre.py [-u URL] [-d DBFILE] [--table TABLE] [--print]

Defaults reproduce the assigned task:
    URL   = https://attack.mitre.org/groups/
    DB    = threat_intel.db
    table = groups

Examples:
    ./scrape_mitre.py
    ./scrape_mitre.py -d threat_intel.db --print
    ./scrape_mitre.py -u https://attack.mitre.org/groups/ -d threat_intel.db

Exit codes:
    0  success (page fetched, table parsed, rows inserted)
    1  fetched but parsed zero rows (structure may have changed)
    2  usage / fatal error (download failed, table not found, cannot write DB)
"""

import argparse
import sqlite3
import sys

import requests
from bs4 import BeautifulSoup

DEFAULT_URL = "https://attack.mitre.org/groups/"
DEFAULT_DB = "threat_intel.db"
DEFAULT_TABLE = "groups"

# Sent so MITRE's front end serves the normal page rather than a bot-challenge.
REQUEST_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

# Column headers we expect on the ATT&CK Groups table, normalized to lowercase.
# We locate columns by these names, not by index, so reordering can't misalign data.
COL_ID = "id"
COL_NAME = "name"
COL_ASSOCIATED = "associated groups"


def fetch_page(url):
    """Download the Groups page and return its HTML.

    Exits 2 with a clear message on any network/HTTP failure so the tool
    reports why it could not do its job.
    """
    try:
        resp = requests.get(url, headers=REQUEST_HEADERS, timeout=30)
        resp.raise_for_status()
    except requests.exceptions.RequestException as exc:
        print(f"error: could not fetch {url} — {exc}", file=sys.stderr)
        raise SystemExit(2)
    return resp.text


def find_groups_table(soup):
    """Return the BeautifulSoup <table> that holds the groups directory.

    Chooses the first table whose header row contains the columns we need.
    Exits 2 if no such table exists (page structure changed / wrong page).
    """
    for table in soup.find_all("table"):
        header_cells = _header_texts(table)
        if COL_ID in header_cells and COL_NAME in header_cells:
            return table
    print("error: no groups table with 'ID' and 'Name' columns found — "
          "the page structure may have changed.", file=sys.stderr)
    raise SystemExit(2)


def _header_texts(table):
    """Return the table's header cell texts, lowercased and stripped."""
    thead = table.find("thead")
    header_row = thead.find("tr") if thead else table.find("tr")
    if not header_row:
        return []
    return [c.get_text(strip=True).lower() for c in header_row.find_all(["th", "td"])]


def parse_rows(table):
    """Extract (group_id, name, associated_groups) tuples from the table.

    Maps header names to column indices so the extraction is position-independent.
    'Associated Groups' is optional per-row (often blank) and stored as '' when absent.
    Rows missing an ID are skipped and counted.
    """
    headers = _header_texts(table)
    idx = {name: i for i, name in enumerate(headers)}

    id_i = idx[COL_ID]
    name_i = idx[COL_NAME]
    assoc_i = idx.get(COL_ASSOCIATED)  # may be absent

    tbody = table.find("tbody")
    body_rows = tbody.find_all("tr") if tbody else table.find_all("tr")[1:]

    rows = []
    skipped = 0
    for tr in body_rows:
        cells = tr.find_all(["td", "th"])
        if len(cells) <= name_i:
            skipped += 1
            continue
        group_id = cells[id_i].get_text(strip=True)
        name = cells[name_i].get_text(strip=True)
        if not group_id:
            skipped += 1
            continue
        if assoc_i is not None and len(cells) > assoc_i:
            # Associated groups is a comma-separated list; normalize whitespace.
            associated = " ".join(cells[assoc_i].get_text(" ", strip=True).split())
        else:
            associated = ""
        rows.append((group_id, name, associated))

    return rows, skipped


def init_db(db_path, table):
    """Create the database and a typed table with a primary key on the group ID.

    Returns an open sqlite3 connection. Uses IF NOT EXISTS so re-runs are safe,
    and INSERT OR REPLACE on write so a re-scrape updates rather than duplicates.
    """
    conn = sqlite3.connect(db_path)
    conn.execute(f"""
        CREATE TABLE IF NOT EXISTS {table} (
            group_id           TEXT PRIMARY KEY,
            name               TEXT NOT NULL,
            associated_groups  TEXT
        )
    """)
    conn.commit()
    return conn


def insert_rows(conn, table, rows):
    """Insert (or replace) scraped rows. Returns the number written."""
    conn.executemany(
        f"INSERT OR REPLACE INTO {table} (group_id, name, associated_groups) "
        f"VALUES (?, ?, ?)",
        rows,
    )
    conn.commit()
    return len(rows)


def print_table(conn, table):
    """Dump the stored rows to stdout for a quick eyeball / verification."""
    cur = conn.execute(
        f"SELECT group_id, name, associated_groups FROM {table} ORDER BY group_id"
    )
    for group_id, name, associated in cur.fetchall():
        assoc = f"  [{associated}]" if associated else ""
        print(f"{group_id}\t{name}{assoc}")


def parse_args(argv):
    parser = argparse.ArgumentParser(
        description="Scrape the MITRE ATT&CK Groups directory into a local SQLite DB.",
    )
    parser.add_argument("-u", "--url", default=DEFAULT_URL,
                        help=f"Groups directory URL (default: {DEFAULT_URL}).")
    parser.add_argument("-d", "--db", default=DEFAULT_DB,
                        help=f"SQLite database file (default: {DEFAULT_DB}).")
    parser.add_argument("--table", default=DEFAULT_TABLE,
                        help=f"Table name (default: {DEFAULT_TABLE}).")
    parser.add_argument("--print", action="store_true", dest="do_print",
                        help="Print the stored rows after inserting.")
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv if argv is not None else sys.argv[1:])

    html = fetch_page(args.url)
    soup = BeautifulSoup(html, "html.parser")
    table = find_groups_table(soup)
    rows, skipped = parse_rows(table)

    if not rows:
        print("error: parsed zero rows from the groups table — "
              "the page structure may have changed.", file=sys.stderr)
        return 1

    conn = init_db(args.db, args.table)
    written = insert_rows(conn, args.table, rows)

    print(f"Scraped {len(rows)} groups -> {args.db} (table: {args.table})",
          file=sys.stderr)
    if skipped:
        print(f"note: skipped {skipped} row(s) with no usable ID", file=sys.stderr)

    if args.do_print:
        print_table(conn, args.table)

    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
