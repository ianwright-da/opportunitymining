# Google Forums Search to Google Sheets

A small Python 3.11+ CLI that reads search queries from the first tab of a Google Sheet, runs each query through the Apify actor `johnvc/google-forums-search-api`, and appends normalized results to the second tab of the same spreadsheet.

## Project structure

```text
main.py            # CLI entry point
config.py          # Environment variable loading and validation
sheets_client.py   # Google Sheets authentication/read/append helpers
apify_client.py    # Requests-based Apify REST API client
normalize.py       # Result field extraction, URL cleanup, and deduplication
requirements.txt   # Runtime Python dependencies
.env.example       # Example environment configuration
README.md          # Setup and usage instructions
```

## Install requirements

Use Python 3.11 or newer.

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

## Create and share Google service account credentials

1. Open the Google Cloud Console.
2. Create or select a Google Cloud project.
3. Enable the **Google Sheets API** for the project.
4. Create a service account in **IAM & Admin → Service Accounts**.
5. Create a JSON key for that service account and download it to your machine.
6. Copy the service account email address from the JSON file or from the Google Cloud Console.
7. Open the Google Sheet you want to process and share it with that service account email address.
8. Give the service account edit access so the CLI can append rows to the results tab.

Keep the JSON key private. Do not commit it to Git.

## Configure `.env`

Copy the example file and edit the values:

```bash
cp .env.example .env
```

Set:

```dotenv
APIFY_TOKEN=apify_api_your_token_here
GOOGLE_CREDS_PATH=/absolute/path/to/service-account.json
```

- `APIFY_TOKEN` is your Apify API token.
- `GOOGLE_CREDS_PATH` is the absolute or `~`-based path to the Google service account JSON key file.

## Expected sheet layout

The spreadsheet must have at least two tabs unless you pass explicit tab names:

1. **Query tab**: defaults to the first tab. Put one search query per row in column `A` by default. Blank rows are ignored.
2. **Results tab**: defaults to the second tab. The CLI appends output rows here.

If the results tab is empty, the CLI writes these headers before appending data:

```text
Query, Title, URL, Snippet, Date, Position, Source, Raw JSON
```

The `Raw JSON` column stores the original Apify dataset item as compact JSON for auditing and future re-processing.

## Usage

Basic example:

```bash
python main.py "https://docs.google.com/spreadsheets/d/..." --limit 10
```

Use custom tabs and query column:

```bash
python main.py "https://docs.google.com/spreadsheets/d/..." \
  --query-tab "Queries" \
  --results-tab "Forum Results" \
  --query-column B
```

Preview without appending rows:

```bash
python main.py "https://docs.google.com/spreadsheets/d/..." --limit 5 --dry-run
```

## CLI options

- `sheet_url` — required Google Sheet URL.
- `--query-tab` — tab containing queries. Defaults to the first sheet.
- `--results-tab` — tab receiving results. Defaults to the second sheet.
- `--query-column` — column containing queries. Defaults to `A`.
- `--limit` — optional maximum number of queries to process.
- `--dry-run` — run the Apify searches and print summary stats without appending rows.
- `--sleep-seconds` — delay between queries to avoid hammering the API. Defaults to `1.0`.

## Apify behavior

For each query, the CLI starts the actor `johnvc/google-forums-search-api` with this input:

```json
{
  "q": "<query>",
  "device": "desktop",
  "safe": "off",
  "nfpr": "0",
  "filter": "0",
  "max_pages": 0
}
```

The CLI polls the actor run until it reaches a terminal status, reads `defaultDatasetId`, and fetches dataset items from Apify. Failed, timed out, and empty runs are reported as warnings, and processing continues with the next query.

## Normalization and deduplication

For each result item, the CLI extracts the best available values for:

- title
- URL or link
- snippet or description
- date
- position or rank

URLs are normalized by removing query strings and fragments. Duplicate normalized URLs are skipped within each query run.

## Output summary

At the end, the CLI prints:

- queries processed
- total results returned
- unique results appended
- failed queries
