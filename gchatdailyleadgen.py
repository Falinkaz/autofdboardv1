# notify_chat.py
import os, sys, argparse, requests, datetime as dt
from zoneinfo import ZoneInfo

API_KEY  = os.environ.get("TRELLO_API_KEY")  or sys.exit("Missing TRELLO_API_KEY")
TOKEN    = os.environ.get("TRELLO_TOKEN")     or sys.exit("Missing TRELLO_TOKEN")
WEBHOOK  = os.environ.get("LEADGEN_WEBHOOK_URL") or sys.exit("Missing LEADGEN_WEBHOOK_URL")

LOCAL_TZ = ZoneInfo("America/Mexico_City")

def previous_business_window_local(tz: ZoneInfo):
    now_local = dt.datetime.now(tz)
    today = now_local.date()
    wd = today.weekday()  # Mon=0..Sun=6
    if wd == 0: delta = 3         # Mon -> Fri
    elif wd == 6: delta = 2       # Sun -> Fri
    elif wd == 5: delta = 1       # Sat -> Fri
    else: delta = 1               # Tue–Fri -> yesterday
    d = today - dt.timedelta(days=delta)
    start_local = dt.datetime(d.year, d.month, d.day, 0, 0, tzinfo=tz)
    end_local   = start_local + dt.timedelta(days=1)
    return (
        start_local.astimezone(dt.timezone.utc).isoformat().replace("+00:00", "Z"),
        end_local.astimezone(dt.timezone.utc).isoformat().replace("+00:00", "Z"),
        d.strftime("%a %b %d")
    )

def window_for_date_local(tz: ZoneInfo, ymd: str):
    d = dt.date.fromisoformat(ymd)
    start_local = dt.datetime(d.year, d.month, d.day, 0, 0, tzinfo=tz)
    end_local   = start_local + dt.timedelta(days=1)
    return (
        start_local.astimezone(dt.timezone.utc).isoformat().replace("+00:00", "Z"),
        end_local.astimezone(dt.timezone.utc).isoformat().replace("+00:00", "Z"),
        d.strftime("%a %b %d")
    )

def fetch_created_card_ids(board_id: str, since_iso_utc: str, before_iso_utc: str):
    url = f"https://api.trello.com/1/boards/{board_id}/actions"
    params = {
        "key": API_KEY, "token": TOKEN,
        "filter": "createCard",
        "since": since_iso_utc, "before": before_iso_utc,
        "limit": 1000,
    }
    r = requests.get(url, params=params, timeout=30); r.raise_for_status()
    ids = []
    for a in r.json():
        cid = ((a.get("data") or {}).get("card") or {}).get("id")
        if cid: ids.append(cid)
    return ids

def fetch_card_owners(card_id: str):
    url = f"https://api.trello.com/1/cards/{card_id}"
    params = {
        "key": API_KEY, "token": TOKEN,
        "fields": "name,labels,idMembers",
        "members": "true", "member_fields": "fullName",
    }
    r = requests.get(url, params=params, timeout=30); r.raise_for_status()
    card = r.json()
    owners = []
    for m in card.get("members") or []:
        full = (m.get("fullName") or "").strip()
        if full: owners.append(full)
    if not owners:
        for lbl in card.get("labels") or []:
            name = (lbl.get("name") or "").strip()
            if name.upper().startswith("OWNER:"):
                owners.append(name.split(":",1)[1].strip() or "Unassigned/Other")
    return owners or ["Unassigned/Other"]

def format_message(title: str, label: str, counts: dict):
    if not counts:
        return f"🔔 {title} — no new cards on {label}."
    lines = [f"🔔 {title} on {label}:"]
    for owner, n in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0].lower())):
        lines.append(f"{owner}: {n}")
    return "\n".join(lines)

def post_to_chat(text: str):
    r = requests.post(WEBHOOK, json={"text": text}, timeout=15)
    r.raise_for_status()

def main():
    p = argparse.ArgumentParser(description="Send Trello daily summary to Google Chat")
    p.add_argument("--board",   default="AQJCiqwE", help="Trello board id/shortLink (default: AQJCiqwE)")
    p.add_argument("--when",    choices=["prev-biz","yesterday","date"], default="prev-biz",
                   help="previous business day (default), yesterday, or a specific date")
    p.add_argument("--date",    help="YYYY-MM-DD (required if --when date)")
    p.add_argument("--title",   default="Focused Prospecting Cards created",
                   help="Message title")
    p.add_argument("--only-owners", nargs="*", default=[],
                   help="If provided, only count these owners (case-insensitive)")
    args = p.parse_args()

    if args.when == "prev-biz":
        since_iso, before_iso, label = previous_business_window_local(LOCAL_TZ)
    elif args.when == "yesterday":
        yday = (dt.datetime.now(LOCAL_TZ).date() - dt.timedelta(days=1)).isoformat()
        since_iso, before_iso, label = window_for_date_local(LOCAL_TZ, yday)
    else:
        if not args.date: sys.exit("--date YYYY-MM-DD required with --when date")
        since_iso, before_iso, label = window_for_date_local(LOCAL_TZ, args.date)

    try:
        card_ids = fetch_created_card_ids(args.board, since_iso, before_iso)
    except requests.HTTPError as e:
        sys.exit(f"Trello actions error: {getattr(e.response,'text',str(e))}")

    counts = {}
    for cid in card_ids:
        try:
            owners = fetch_card_owners(cid)
        except requests.HTTPError as e:
            print(f"Warn: card fetch failed for {cid}: {getattr(e.response,'text',str(e))}", file=sys.stderr)
            continue
        for owner in owners:
            counts[owner] = counts.get(owner, 0) + 1

    if args.only_owners:
        allow = {s.strip().lower() for s in args.only_owners}
        counts = {k:v for k,v in counts.items() if k.strip().lower() in allow}

    text = format_message(args.title, label, counts)

    try:
        post_to_chat(text)
        print("✅ Posted summary to Google Chat.")
    except requests.HTTPError as e:
        sys.exit(f"Chat webhook error: {getattr(e.response,'text',str(e))}")

if __name__ == "__main__":
    main()
