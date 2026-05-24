"""
ΕΜΒΟΛΙΑ — Daily Supabase → Google Sheets Backup
Fetches all rows from emvolia and emvolia_history and writes to Google Sheets.
Runs via GitHub Actions every night.
"""

import os
import json
import requests
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime, timezone

# ── CONFIG ────────────────────────────────────────────────────────
SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_KEY"]
SHEET_ID     = os.environ["SHEET_ID"]

SB_HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
}

# ── COLUMN DEFINITIONS ────────────────────────────────────────────
DATA_COLUMNS = [
    "id", "emvolio", "hm_ekk", "hm_emv", "hm_par", "hm_paragelia",
    "anath", "pelatis", "posotita", "sxolia_panos", "sxolia_eleni",
    "promitheutis", "paragelia", "psygeio",
    "created_by", "created_at", "updated_by", "updated_at",
]
DATA_HEADERS = [
    "ID", "ΕΜΒΟΛΙΟ", "ΗΜ. ΕΚΚΟΛΑΨΗΣ", "ΗΜ. ΕΜΒΟΛΙΑΣΜΟΥ", "ΗΜ. ΚΑΤΑΧΩΡΗΣΗΣ",
    "ΗΜ. ΠΑΡΑΓΓΕΛΙΑΣ", "ΑΝΑΘΡΕΠΤΗΡΙΟ", "ΠΕΛΑΤΗΣ", "ΠΟΣΟΤΗΤΑ",
    "ΣΧΟΛΙΑ ΠΑΝΟΣ", "ΣΧΟΛΙΑ ΕΛΕΝΗ", "ΠΡΟΜΗΘΕΥΤΗΣ", "ΠΑΡΑΓΓΕΛΙΑ", "ΨΥΓΕΙΟ",
    "ΔΗΜΙΟΥΡΓΗΘΗΚΕ ΑΠΟ", "ΔΗΜΙΟΥΡΓΗΘΗΚΕ", "ΕΠΕΞΕΡΓΑΣΤΗΚΕ ΑΠΟ", "ΕΠΕΞΕΡΓΑΣΤΗΚΕ",
]

HISTORY_COLUMNS = ["id", "row_id", "action", "user_name", "ts", "changes_json"]
HISTORY_HEADERS = ["ID", "ROW ID", "ΕΝΕΡΓΕΙΑ", "ΧΡΗΣΤΗΣ", "ΧΡΟΝΟΣ", "ΑΛΛΑΓΕΣ (JSON)"]

# ── FETCH ─────────────────────────────────────────────────────────
def fetch(table, order):
    url = f"{SUPABASE_URL}/rest/v1/{table}?order={order}"
    r = requests.get(url, headers=SB_HEADERS, timeout=30)
    r.raise_for_status()
    rows = r.json()
    print(f"  ✓ Fetched {len(rows)} rows from '{table}'")
    return rows

# ── WRITE SHEET TAB ───────────────────────────────────────────────
def write_tab(sh, title, columns, headers, rows, header_col_count):
    try:
        ws = sh.worksheet(title)
    except gspread.WorksheetNotFound:
        ws = sh.add_worksheet(title=title, rows=10000, cols=len(columns))

    data = [headers] + [[str(r.get(c, "") or "") for c in columns] for r in rows]
    ws.clear()
    ws.update("A1", data, value_input_option="RAW")

    col_letter = chr(ord('A') + header_col_count - 1)
    ws.format(f"A1:{col_letter}1", {
        "textFormat": {"bold": True},
        "backgroundColor": {"red": 0.13, "green": 0.11, "blue": 0.14},
    })
    print(f"  ✓ Wrote {len(rows)} rows to '{title}' tab")
    return len(rows)

# ── MAIN ──────────────────────────────────────────────────────────
def run_backup():
    print("Connecting to Google Sheets…")
    creds = Credentials.from_service_account_info(
        json.loads(os.environ["GOOGLE_CREDENTIALS"]),
        scopes=[
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive",
        ]
    )
    gc = gspread.authorize(creds)
    sh = gc.open_by_key(SHEET_ID)
    print("  ✓ Connected")

    print("\nFetching data from Supabase…")
    emvolia = fetch("emvolia", "hm_emv.asc")
    history = fetch("emvolia_history", "ts.desc")

    print("\nWriting to Google Sheets…")
    n_data    = write_tab(sh, "Δεδομένα",  DATA_COLUMNS,    DATA_HEADERS,    emvolia, len(DATA_COLUMNS))
    n_history = write_tab(sh, "Ιστορικό",  HISTORY_COLUMNS, HISTORY_HEADERS, history, len(HISTORY_COLUMNS))

    # ── LOG ───────────────────────────────────────────────────────
    try:
        log_ws = sh.worksheet("Log")
    except gspread.WorksheetNotFound:
        log_ws = sh.add_worksheet(title="Log", rows=1000, cols=5)
        log_ws.update("A1", [["Timestamp", "Εγγραφές", "Ιστορικό", "Status", "Notes"]])
        log_ws.format("A1:E1", {"textFormat": {"bold": True}})

    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    log_ws.append_row([ts, n_data, n_history, "✓ Success", ""])
    print(f"\n  ✓ Logged at {ts}")
    return n_data, n_history

if __name__ == "__main__":
    print("═" * 50)
    print("ΕΜΒΟΛΙΑ Daily Backup")
    print("═" * 50)
    try:
        n_data, n_history = run_backup()
        print(f"\n✓ Backup complete — {n_data} εγγραφές, {n_history} ιστορικό")
    except Exception as e:
        print(f"\n✗ Backup failed: {e}")
        # Attempt to log failure to sheet
        try:
            creds = Credentials.from_service_account_info(
                json.loads(os.environ.get("GOOGLE_CREDENTIALS", "{}")),
                scopes=["https://www.googleapis.com/auth/spreadsheets"]
            )
            gc = gspread.authorize(creds)
            sh = gc.open_by_key(os.environ["SHEET_ID"])
            log_ws = sh.worksheet("Log")
            ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
            log_ws.append_row([ts, 0, 0, "✗ Failed", str(e)])
        except Exception:
            pass
        raise
