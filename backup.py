"""
ΕΜΒΟΛΙΑ — Daily Supabase → Google Sheets Backup
Fetches all rows from the emvolia table and writes them to a Google Sheet.
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

# Column order — must match Google Sheet headers
COLUMNS = [
    "id", "emvolio", "hm_ekk", "hm_emv", "hm_par", "hm_paragelia",
    "anath", "pelatis", "posotita", "sxolia_panos", "sxolia_eleni",
    "promitheutis", "paragelia", "psygeio",
    "created_by", "created_at", "updated_by", "updated_at",
]

HEADERS_GR = [
    "ID", "ΕΜΒΟΛΙΟ", "ΗΜ. ΕΚΚΟΛΑΨΗΣ", "ΗΜ. ΕΜΒΟΛΙΑΣΜΟΥ", "ΗΜ. ΚΑΤΑΧΩΡΗΣΗΣ",
    "ΗΜ. ΠΑΡΑΓΓΕΛΙΑΣ", "ΑΝΑΘΡΕΠΤΗΡΙΟ", "ΠΕΛΑΤΗΣ", "ΠΟΣΟΤΗΤΑ",
    "ΣΧΟΛΙΑ ΠΑΝΟΣ", "ΣΧΟΛΙΑ ΕΛΕΝΗ", "ΠΡΟΜΗΘΕΥΤΗΣ", "ΠΑΡΑΓΓΕΛΙΑ", "ΨΥΓΕΙΟ",
    "ΔΗΜΙΟΥΡΓΗΘΗΚΕ ΑΠΟ", "ΔΗΜΙΟΥΡΓΗΘΗΚΕ", "ΕΠΕΞΕΡΓΑΣΤΗΚΕ ΑΠΟ", "ΕΠΕΞΕΡΓΑΣΤΗΚΕ",
]

# ── FETCH FROM SUPABASE ───────────────────────────────────────────
def fetch_data():
    url = f"{SUPABASE_URL}/rest/v1/emvolia?order=hm_emv.asc"
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
    }
    response = requests.get(url, headers=headers, timeout=30)
    response.raise_for_status()
    data = response.json()
    print(f"✓ Fetched {len(data)} rows from Supabase")
    return data

# ── WRITE TO GOOGLE SHEETS ────────────────────────────────────────
def write_to_sheet(data):
    creds_json = json.loads(os.environ["GOOGLE_CREDENTIALS"])
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]
    creds = Credentials.from_service_account_info(creds_json, scopes=scopes)
    gc = gspread.authorize(creds)
    sh = gc.open_by_key(SHEET_ID)

    # ── DATA SHEET ────────────────────────────────────────────────
    try:
        ws = sh.worksheet("Δεδομένα")
    except gspread.WorksheetNotFound:
        ws = sh.add_worksheet(title="Δεδομένα", rows=5000, cols=len(COLUMNS))

    # Build rows: header + data
    rows = [HEADERS_GR]
    for row in data:
        rows.append([str(row.get(col, "") or "") for col in COLUMNS])

    # Clear and rewrite
    ws.clear()
    ws.update("A1", rows, value_input_option="RAW")

    # Bold the header row
    ws.format("A1:R1", {
        "textFormat": {"bold": True},
        "backgroundColor": {"red": 0.13, "green": 0.11, "blue": 0.14},
    })

    print(f"✓ Wrote {len(data)} rows to 'Δεδομένα' sheet")

    # ── LOG SHEET ─────────────────────────────────────────────────
    try:
        log_ws = sh.worksheet("Log")
    except gspread.WorksheetNotFound:
        log_ws = sh.add_worksheet(title="Log", rows=1000, cols=4)
        log_ws.update("A1", [["Timestamp", "Rows", "Status", "Notes"]])
        log_ws.format("A1:D1", {"textFormat": {"bold": True}})

    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    log_ws.append_row([timestamp, len(data), "✓ Success", ""])
    print(f"✓ Logged backup run at {timestamp}")

# ── MAIN ──────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("Starting ΕΜΒΟΛΙΑ backup...")
    try:
        data = fetch_data()
        write_to_sheet(data)
        print(f"\n✓ Backup complete — {len(data)} rows saved to Google Sheets")
    except Exception as e:
        # Log the failure too
        print(f"\n✗ Backup failed: {e}")
        try:
            creds_json = json.loads(os.environ.get("GOOGLE_CREDENTIALS", "{}"))
            if creds_json:
                scopes = ["https://www.googleapis.com/auth/spreadsheets"]
                creds = Credentials.from_service_account_info(creds_json, scopes=scopes)
                gc = gspread.authorize(creds)
                sh = gc.open_by_key(os.environ["SHEET_ID"])
                log_ws = sh.worksheet("Log")
                timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
                log_ws.append_row([timestamp, 0, "✗ Failed", str(e)])
        except Exception:
            pass  # If even logging fails, the GitHub Actions log has the error
        raise  # Re-raise so GitHub Actions marks the run as failed
