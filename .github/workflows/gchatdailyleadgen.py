# .github/workflows/gchat-daily-leadgen.yml
name: Send Google Chat daily summary (LeadGen)

on:
  schedule:
    - cron: "0 15 * * 1-5"   # 09:00 America/Mexico_City, Mon–Fri
  workflow_dispatch: {}       # allow manual runs

concurrency:
  group: gchat-leadgen
  cancel-in-progress: false

jobs:
  run:
    runs-on: ubuntu-latest
    permissions:
      contents: read
    env:
      TRELLO_API_KEY: ${{ secrets.TRELLO_API_KEY }}
      TRELLO_TOKEN: ${{ secrets.TRELLO_TOKEN }}
      LEADGEN_WEBHOOK_URL: ${{ secrets.LEADGEN_WEBHOOK_URL }}  # make sure this secret exists
    steps:
      - name: Checkout repo
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - name: Install deps
        run: python -m pip install --upgrade pip requests

      - name: Post daily summary to LeadGen Chat
        run: python gchatdailyleadgen.py --when prev-biz --only-owners "Abraham Del Carmen" "Mariana Esparza"
