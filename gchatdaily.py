# gchatdaily.py (or notify_chat_daily.py)
import os
import sys
import requests
import datetime as dt
from zoneinfo import ZoneInfo

API_KEY  = os.environ.get("TRELLO_API_KEY")  or sys.exit("Missing TRELLO_API_KEY")
TOKEN    = os.environ.get("TRELLO_TOKEN")     or sys.exit("Missing TRELLO_TOKEN")
WEBHOOK  = os.environ.get("GOOGLE_CHAT_WEBHOOK_URL") or sys.exit("Missing GOOGLE_CHAT_WEBHOOK_URL")

BOARD_ID = "AQJCiqwE"  # your selected board
LOCAL_TZ = ZoneInfo("America/Mexico_City")

def day_window_previous_local(tz: ZoneInfo):
    now_local = dt.datetime.now(tz)
    yday = now_local.date() - dt.timedelta(days=1)
    start_local = dt.datetime(yday.year, yday.month, yday.day, 0, 0, 0, tzinfo=tz)
    end_local   = start_local + dt.timedelta(days=1)
    start_utc = start_local.astimezone(dt.timezone.utc)
    end_utc   = end_local.astimezone(dt.timezone.utc)
    return (
        start_utc.isoformat().replace("+00:00", "Z"),
        end_utc.isoformat().replace("+00:00", "Z"),
        yday.strftime("%a %b %d"),
    )

def fetch_created_card_ids(board_id: str, since_iso_utc: str, before_iso_utc: str):
    url = f"https://api.trello.com/1/boards/{board_id}/actions"
    params = {
        "key": API_KEY,
        "token": TOKEN,
        "filter": "createCard",
        "since": since_iso_utc,
        "before": before_iso_utc,
        "limit": 1000,
    }
    r = requests.get(url, params=params, timeout=30)
    r.raise_for_status()
    actions = r.json()
    ids = []
    for a in actions:
        d = a.get("data", {})
        card = d.get("card") or {}
        cid = card.get("id")
        if cid:
            ids.append(cid)
    return ids

def fetch_card_owners(card_id: str):
    url = f"https://api.trello.com/1/cards/{card_id}"
    params = {
        "key": API_KEY,
        "token": TOKEN,
        "fields": "name,labels,idMembers",
        "members": "true",
        "member_fields": "fullName",
    }
    r = requests.get(url, params=params, timeout=30)
    r.raise_for_status()
    card = r.json()

    owners = []
    for m in card.get("members") or []:
        full = (m.get("fullName") or "").strip()
        if full:
            owners.append(full)

    if not owners:
        for lbl in card.get("labels") or []:
            name = (lbl.get("name") or "").strip()
            if name.upper().startswith("OWNER:"):
                val = name.split(":", 1)[1].strip() if ":" in name else name
                if val:
                    owners.append(val)

    if not owners:
        owners = ["Unassigned/Other"]

    return owners

def post_to_chat(text: str):
    resp = requests.post(WEBHOOK, json={"text": text}, timeout=15)
    resp.raise_for_status()

def format_message(label, counts):
    if not counts:
        return f"🔔 Focused Prospecting — no new cards on {label}."
    header = f"🔔 Focused Prospecting Cards created on {label}:"
    lines = [header]
    for owner, n in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0].lower())):
        lines.append(f"{owner}: {n}")
    return "\n".join(lines)

def main():
    since_iso, before_iso, label = day_window_previous_local(LOCAL_TZ)

    try:
        card_ids = fetch_created_card_ids(BOARD_ID, since_iso, before_iso)
    except requests.HTTPError as e:
        msg = e.response.text if e.response is not None else str(e)
        print(f"❌ Trello actions error: {msg}", file=sys.stderr)
        sys.exit(1)

    counts = {}
    for cid in card_ids:
        try:
            owners = fetch_card_owners(cid)
        except requests.HTTPError as e:
            msg = e.response.text if e.response is not None else str(e)
            print(f"❌ Trello card error for {cid}: {msg}", file=sys.stderr)
            continue
        for owner in owners:
            counts[owner] = counts.get(owner, 0) + 1

    text = format_message(label, counts)

    try:
        post_to_chat(text)
        print("✅ Posted summary to Google Chat.")
    except requests.HTTPError as e:
        msg = e.response.text if e.response is not None else str(e)
        print(f"❌ Chat webhook error: {msg}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
