import argparse
import json
from datetime import datetime, timedelta

def generate_query(start_date, end_date, ticker_list):
    """
    Generates a Google Sheets query string for fetching stock data.

    Args:
        start_date (str): The start date in YYYY-MM-DD format.
        end_date (str): The end date in YYYY-MM-DD format.
        ticker_list (list): A list of ticker symbols.

    Returns:
        str: The formatted Google Sheets query string.
    """
    # Header
    query_parts = [
        '={\n  {"Ticker", "Date", "Open", "High", "Low", "Close", "Volume"};'
    ]

    # Add a query for each ticker
    for ticker in ticker_list:
        prefixed_ticker = f"NASDAQ:{ticker}"
        query_parts.append(
            f'\n  QUERY(\n    GOOGLEFINANCE("{prefixed_ticker}", "all", "{start_date}", "{end_date}", "DAILY"),\n    "SELECT \'{prefixed_ticker}\', Col1, Col2, Col3, Col4, Col5, Col6 OFFSET 1", 0\n  )'
        )

    # Join with semicolons
    header = query_parts[0]
    queries = ";\n".join(query_parts[1:])
    return f"{header}\n{queries}\n}}"

def main():
    """
    Main function to parse arguments and generate the query.
    """
    parser = argparse.ArgumentParser(
        description="Generate a Google Sheets query for stock data."
    )
    parser.add_argument(
        "--start-date",
        type=str,
        default=(datetime.now() - timedelta(days=365)).strftime('%Y-%m-%d'),
        help="Start date in YYYY-MM-DD format."
    )
    parser.add_argument(
        "--end-date",
        type=str,
        default=(datetime.now() + timedelta(days=7)).strftime('%Y-%m-%d'),
        help="End date in YYYY-MM-DD format."
    )
    parser.add_argument(
        "--ticker-list",
        type=str,
        default=None,
        help="A space-separated string of ticker symbols."
    )
    args = parser.parse_args()

    # Get tickers
    if args.ticker_list:
        tickers = args.ticker_list.split()
    else:
        try:
            with open('data/US_ticker_categories.json', 'r') as f:
                data = json.load(f)
                tickers = sorted(list(set(
                    ticker for sublist in data.values() for ticker in sublist
                )))
        except FileNotFoundError:
            print("Error: 'data/US_ticker_categories.json' not found.")
            return

    # Generate and print the query
    query = generate_query(args.start_date, args.end_date, tickers)
    print(query)

if __name__ == "__main__":
    main()