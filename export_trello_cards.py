import os
import requests
import csv

API_KEY = os.environ['TRELLO_API_KEY']
TOKEN = os.environ['TRELLO_TOKEN']

BOARD_IDS = {
    "vkpjS0Dm": "Board 1",
    "AQJCiqwE": "Board 2"
}

OUTPUT_CSV = 'cards_export.csv'

def get_cards_from_board(board_id, board_name):
    url = f'https://api.trello.com/1/boards/{board_id}/cards'
    params = {
        'key': API_KEY,
        'token': TOKEN,
        'fields': 'name'
    }
    response = requests.get(url, params=params)
    response.raise_for_status()
    data = response.json()
    return [(card['name'], board_name) for card in data if not card.get('closed', False)]

def main():
    all_cards = []

    for board_id, board_name in BOARD_IDS.items():
        print(f'📦 Fetching cards from {board_name}...')
        cards = get_cards_from_board(board_id, board_name)
        all_cards.extend(cards)

    with open(OUTPUT_CSV, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['card_name', 'board_name'])
        writer.writerows(all_cards)

    print(f'\n✅ Done! Exported {len(all_cards)} cards to {OUTPUT_CSV}')

if __name__ == '__main__':
    main()
