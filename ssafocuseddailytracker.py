import os
import csv
import sys
import requests
import datetime as dt
from zoneinfo import ZoneInfo

# --- Your existing variables (kept) ---
API_KEY = os.environ['TRELLO_API_KEY']
TOKEN   = os.environ['TRELLO_TOKEN']

BOARD_IDS = {
    "vkpjS0Dm": "Board 1",
    "AQJCiqwE": "Board 2"
}

OUTPUT_CSV = 'dailytracker.csv'
# --------------------------------------

# Only use this board (as requested)
SELECTED_BOARD_ID = "AQJCiqwE"
LOCAL_TZ = ZoneInfo("America/Mexico_City")

def trello_id_creation_dt(card_id: str) -> dt.datetime:
    """Trello IDs: first 8 hex chars = Unix timestamp (seconds, UTC) -> aware UTC dt."""
    epoch = int(card_id[:8], 16)
    return dt.datetime.utcfromtimestamp(epoch).replace(tzinfo=dt.timezone.utc)

def monday_of_week(local_dt: dt.datetime) -> dt.date:
    """Return Monday date for the week of local_dt."""
    d = local_dt.date()
    return d - dt.timedelta(days=d.weekday())

def fmt_month_day(d: dt.date) -> str:
    """Format like 'Sep 15'."""
    return d.strftime("%b %d")

def get_cards_from_board(board_id, board_name):
    """
    Returns a list of tuples: (card_name, board_name, owner, week_created)
    - owner: assigned members' full names joined by '; ', falling back to any 'OWNER: ...' label
    - week_created: Monday of creation week in America/Mexico_City, formatted 'Mon D' (e.g., 'Sep 15')
    """
    url = f'https://api.trello.com/1/boards/{board_id}/cards'
    params = {
        'key': API_KEY,
        'token': TOKEN,
        'filter': 'open',
        # we need id (for creation time), idMembers, labels, and name
        'fields': 'name,id,idMembers,labels',
        # include full member objects on each card so we can show names
        'members': 'true',
        'member_fields': 'fullName,username'
    }
    resp = requests.get(url, params=params, timeout=30)
    resp.raise_for_status()
    data = resp.json()

    rows = []
    for card in data:
        if card.get('closed'):
            continue

        card_name = card.get('name', '').strip()
        if not card_name:
            continue

        # Owner(s): prefer assigned members
        owner_names = []
        for m in card.get('members', []) or []:
            fn = (m.get('fullName') or '').strip()
            if fn:
                owner_names.append(fn)

        # Fallback to OWNER label if no members
        if not owner_names:
            for lbl in card.get('labels', []) or []:
                lbl_name = (lbl.get('name') or '').strip()
                if lbl_name.upper().startswith('OWNER:'):
                    # take text after 'OWNER:' (or the whole label if you prefer)
                    owner_text = lbl_name.split(':', 1)[1].strip() if ':' in lbl_name else lbl_name
                    if owner_text:
                        owner_names.append(owner_text)

        owner = '; '.join(owner_names)

        # Week created (derive creation time from card id, convert to MX time, get Monday)
        cid = card.get('id', '')
        created_local = trello_id_creation_dt(cid).astimezone(LOCAL_TZ)
        week_monday = monday_of_week(created_local)
        week_created = fmt_month_day(week_monday)  # e.g., 'Sep 15'

        rows.append((card_name, board_name, owner, week_created))

    return rows

def main():
    if SELECTED_BOARD_ID not in BOARD_IDS:
        print(f"❌ The selected board ID '{SELECTED_BOARD_ID}' is not in BOARD_IDS.", file=sys.stderr)
        sys.exit(1)

    selected = {SELECTED_BOARD_ID: BOARD_IDS[SELECTED_BOARD_ID]}
    all_rows = []

    for board_id, board_name in selected.items():
        print(f'📦 Fetching cards from {board_name} ({board_id})...')
        try:
            rows = get_cards_from_board(board_id, board_name)
            all_rows.extend(rows)
            print(f'   → Retrieved {len(rows)} open cards.')
        except requests.HTTPError as e:
            msg = e.response.text if e.response is not None else str(e)
            print(f'❌ HTTP error for board {board_id}: {msg}', file=sys.stderr)
            sys.exit(1)
        except Exception as e:
            print(f'❌ Unexpected error for board {board_id}: {e}', file=sys.stderr)
            sys.exit(1)

    # Write CSV with the new columns
    with open(OUTPUT_CSV, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['card_name', 'board_name', 'owner', 'week_created'])
        writer.writerows(all_rows)

    print(f'\n✅ Done! Exported {len(all_rows)} cards to {OUTPUT_CSV}')

if __name__ == '__main__':
    main()
