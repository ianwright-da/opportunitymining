"""CLI entry point for appending Apify Google forum search results to a Sheet."""

from __future__ import annotations

import argparse
import sys
import time
from dataclasses import dataclass



@dataclass
class RunStats:
    queries_processed: int = 0
    total_results_returned: int = 0
    unique_results_appended: int = 0
    failed_queries: int = 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Read queries from a Google Sheet, run them through the Apify "
            "Google forums search actor, and append results to another tab."
        )
    )
    parser.add_argument("sheet_url", help="Google Sheet URL")
    parser.add_argument(
        "--query-tab",
        default=None,
        help="Worksheet/tab containing queries. Defaults to the first sheet.",
    )
    parser.add_argument(
        "--results-tab",
        default=None,
        help="Worksheet/tab for results. Defaults to the second sheet.",
    )
    parser.add_argument(
        "--query-column",
        default="A",
        help="Column containing queries. Defaults to A.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Optional maximum number of queries to process.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run searches and print stats without appending rows to the Sheet.",
    )
    parser.add_argument(
        "--sleep-seconds",
        type=float,
        default=1.0,
        help="Seconds to sleep between queries. Defaults to 1.0.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    try:
        from tqdm import tqdm

        from apify_client import ACTOR_ID, ApifyClient, ApifyError
        from config import load_config
        from normalize import normalize_results
        from sheets_client import SheetsClient
    except ImportError as exc:
        print(
            f"Error: missing Python dependency ({exc}). "
            "Install dependencies with: python -m pip install -r requirements.txt",
            file=sys.stderr,
        )
        return 1
    if args.limit is not None and args.limit < 1:
        print("Error: --limit must be a positive integer", file=sys.stderr)
        return 2
    if args.sleep_seconds < 0:
        print("Error: --sleep-seconds must be zero or greater", file=sys.stderr)
        return 2

    try:
        config = load_config()
        sheets_client = SheetsClient(config.google_creds_path)
        spreadsheet = sheets_client.open_by_url(args.sheet_url)
        query_ws = sheets_client.get_worksheet(spreadsheet, args.query_tab, default_index=0)
        results_ws = sheets_client.get_worksheet(spreadsheet, args.results_tab, default_index=1)
        queries = sheets_client.read_queries(query_ws, args.query_column, args.limit)
    except Exception as exc:  # noqa: BLE001 - CLI should print concise startup failures.
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    if not queries:
        print("No nonblank queries found.")
        print_summary(RunStats())
        return 0

    apify_client = ApifyClient(config.apify_token)
    stats = RunStats()
    rows_to_append: list[list[object]] = []

    for query in tqdm(queries, desc="Processing queries", unit="query"):
        try:
            raw_items = apify_client.search_forums(query)
            normalized_rows = normalize_results(query, raw_items, source=ACTOR_ID)
        except ApifyError as exc:
            stats.failed_queries += 1
            print(f"Warning: query failed ({query!r}): {exc}", file=sys.stderr)
            if args.sleep_seconds:
                time.sleep(args.sleep_seconds)
            continue
        except Exception as exc:  # noqa: BLE001 - continue to next query by requirement.
            stats.failed_queries += 1
            print(f"Warning: unexpected failure for query ({query!r}): {exc}", file=sys.stderr)
            if args.sleep_seconds:
                time.sleep(args.sleep_seconds)
            continue

        stats.queries_processed += 1
        stats.total_results_returned += len(raw_items)
        stats.unique_results_appended += len(normalized_rows)
        rows_to_append.extend(normalized_rows)

        if not raw_items:
            print(f"Warning: query returned no results ({query!r})", file=sys.stderr)

        if args.sleep_seconds:
            time.sleep(args.sleep_seconds)

    if args.dry_run:
        print(f"Dry run: skipped appending {len(rows_to_append)} row(s) to the results tab.")
    else:
        try:
            sheets_client.ensure_results_header(results_ws)
            sheets_client.append_rows(results_ws, rows_to_append)
        except Exception as exc:  # noqa: BLE001 - final write failure should be clear.
            print(f"Error appending results to Google Sheet: {exc}", file=sys.stderr)
            return 1

    print_summary(stats)
    return 0


def print_summary(stats: RunStats) -> None:
    print("\nSummary")
    print(f"queries processed: {stats.queries_processed}")
    print(f"total results returned: {stats.total_results_returned}")
    print(f"unique results appended: {stats.unique_results_appended}")
    print(f"failed queries: {stats.failed_queries}")


if __name__ == "__main__":
    raise SystemExit(main())
