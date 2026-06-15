"""
This script fetches stock data for a given ticker and date, retrieves currency exchange rates,
and generates a report that combines the stock data with the exchange rates to show prices in different currencies.

Instructions:
1. Set up your environment and create a `.env` file with your Polygon API key.
2. Run the script from the command line with the required arguments:
   - `-t` or `--ticker`: Stock ticker symbol (e.g., AAPL)
   - `-d` or `--date`: Date for fetching stock data (e.g., 2024-10-03)
   - `-s` or `--symbols`: Optional list of currencies to convert the stock prices to (e.g., EUR GBP), otherwise you will get all available currencies.
3. The script will fetch the stock data from the Polygon API, retrieve the exchange rates, and generate a report showing the converted stock prices.
"""

import argparse
import logging
import os
from dotenv import load_dotenv
import requests
import pandas as pd
load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
API_KEY = os.getenv("API_KEY")
if not API_KEY:
    logging.error("POLYGON_API_KEY is missing from .env file")
    raise ValueError("POLYGON_API_KEY is missing")


def fetch_stock_data(ticker: str, date: str, adjusted=True, api_key=API_KEY) -> pd.DataFrame:
    """
    Fetches stock data for a given ticker and date from the Polygon API.

    Returns:
        pd.DataFrame: A DataFrame containing stock data if available, otherwise an empty DataFrame.
    """
    url = f"https://api.polygon.io/v1/open-close/{ticker}/{date}?adjusted={str(adjusted).lower()}&apiKey={api_key}"
    logging.info(f"Fetching stock data for {ticker} on {date} from {url}")

    try:
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()

        if isinstance(data, dict) and "open" in data and "close" in data:
            return pd.DataFrame([data])

        logging.warning(f"No trading data available for {ticker} on {date}. Response: {data}")

    except (requests.exceptions.Timeout, requests.exceptions.RequestException) as e:
        logging.error(f"Network error fetching stock data for {ticker} on {date}: {e}")

    except ValueError as e:
        logging.error(f"Invalid JSON response for {ticker} on {date}: {e}")

    return None


def fetch_currency_name(ticker: str, api_key=API_KEY) -> str:
    """
    Fetches the currency name in which a given stock ticker is traded from the Polygon API.

    Parameters:
        ticker (str): The stock ticker symbol (e.g., "AAPL").
        api_key (str, optional): The API key for authentication. Defaults to API_KEY.

    Returns:
        Optional[str]: The currency name (e.g., "USD") if found, otherwise None.

    Raises:
        ValueError: If the currency information for the given ticker is not found.
    """
    url = f"https://api.polygon.io/v3/reference/tickers/{ticker}?apiKey={api_key}"

    try:
        response = requests.get(url)

        if response.status_code == 200:
            data = response.json()

            if 'results' in data and 'currency_name' in data['results']:
                currency_name = data['results']['currency_name']
                logging.info(f"Currency name for ticker {ticker}: {currency_name}")
                return currency_name
            else:
                error_message = f"Currency information for {ticker} not found."
                logging.error(error_message)
                raise ValueError(error_message)
        else:
            error_message = f"Error fetching data: {response.status_code}, {response.text}"
            logging.error(error_message)
            return ""

    except Exception as e:
        logging.exception(f"An error occurred while fetching currency name for {ticker}: {str(e)}")
        return None


def create_price_types_df(df: pd.DataFrame) -> pd.DataFrame:
    """
    Transforms a DataFrame with separate price columns into a long format
    with 'price_type' and 'price' columns.

    Parameters:
        df (pd.DataFrame): A DataFrame containing price data with columns such as
                            'open', 'high', 'low', 'close', 'afterHours', 'preMarket',
                            and other relevant columns.

    Returns:
        pd.DataFrame: A long-format DataFrame with columns 'ticker', 'date', 'price_type', and 'price'.

    Example:
        create_price_types_df(df)
        Returns:
            pd.DataFrame:
                ticker  date     price_type   price
            0   AAPL    2025-03-01  open        150.0
            1   AAPL    2025-03-01  high        155.0
            2   AAPL    2025-03-01  low         148.0
            3   AAPL    2025-03-01  close       152.0
    """
    try:
        df = df.rename(columns={"afterHours": "after_hours", "preMarket": "pre_market"})
        price_columns = ["open", "high", "low", "close", "after_hours", "pre_market"]
        available_columns = [col for col in price_columns if col in df.columns]

        if not available_columns:
            logging.warning("No price columns found in the provided DataFrame.")
            return pd.DataFrame(columns=["ticker", "date", "price_type", "price"])

        df_long = df.melt(id_vars=["symbol", "from"],
                           value_vars=available_columns,
                           var_name="price_type",
                           value_name="price")
        df_long = df_long.rename(columns={"symbol": "ticker", "from": "date"})

        logging.info("Successfully transformed the DataFrame into long format.")
        return df_long

    except Exception as e:
        logging.exception(f"An error occurred while transforming the DataFrame: {str(e)}")
        return None



def fetch_latest_currency_rates(base_currency: str, symbols: [str], date: [str]) -> pd.DataFrame:
    """
    Fetches the latest currency exchange rates for a given base currency and date.

    Parameters:
        base_currency (str): The base currency code (e.g., "USD").
        symbols (list[str]): A list of target currency codes (e.g., ["EUR", "GBP"]). If empty, all available currencies are fetched.
        date (str): The date for which the exchange rates are requested (in "YYYY-MM-DD" format).

    Returns:
        pd.DataFrame: A DataFrame containing the currency codes and their respective exchange rates.

    Example:
        fetch_latest_currency_rates("USD", ["EUR", "GBP"], "2025-03-01")
        Returns:
            pd.DataFrame:
                currency   exchange_rate
            0   EUR        0.82
            1   GBP        0.74
    """
    if not symbols:
        url = f"https://api.frankfurter.dev/v1/{date}?base={base_currency}"
    else:
        symbols_str = ','.join(symbols)
        url = f"https://api.frankfurter.dev/v1/{date}?base={base_currency}&symbols={symbols_str}"

    try:
        response = requests.get(url)

        if response.status_code == 200:
            data = response.json()
            rates = data.get("rates", {})

            df_latest_currency_rate = pd.DataFrame(list(rates.items()), columns=["currency", "exchange_rate"])
            logging.info(f"Successfully fetched exchange rates for {base_currency} on {date}.")
            return df_latest_currency_rate
        else:
            error_message = f"Error fetching data: {response.status_code}, {response.text}"
            logging.error(error_message)
            return pd.DataFrame(columns=["currency", "exchange_rate"])

    except Exception as e:
        logging.exception(f"An error occurred while fetching exchange rates for {base_currency} on {date}: {str(e)}")
        return None


def fetch_available_currencies() -> pd.DataFrame:
    """
    Fetches a list of available currencies from the Frankfurter API.

    Returns:
        Optional[Dict[str, str]]: A dictionary where keys are currency codes (e.g., "USD")
        and values are currency names (e.g., "United States Dollar"). Returns None if the request fails.

    Example:
        {
            "USD": "United States Dollar",
            "EUR": "Euro",
            "GBP": "British Pound"
        }
    """
    url = "https://api.frankfurter.dev/v1/currencies"

    try:
        response = requests.get(url)

        if response.status_code == 200:
            df_available_currencies = response.json()
            logging.info("Successfully fetched available currencies.")
            return pd.DataFrame(df_available_currencies.items(), columns=["Currency Code", "Currency Name"])
        else:
            error_message = f"Error fetching data: {response.status_code}, {response.text}"
            logging.error(error_message)
            return pd.DataFrame(columns=["Currency Code", "Currency Name"])

    except Exception as e:
        logging.exception(f"An error occurred while fetching available currencies: {str(e)}")
        return None


def create_stock_currency_report(stock_df_long: pd.DataFrame, exchange_rates_df: pd.DataFrame, stock_currency: str) -> pd.DataFrame:
    """
    Creates a stock currency report by combining stock price data with exchange rates.

    Parameters:
        stock_df_long (DataFrame): Contains ticker, date, price_type, and price.
        exchange_rates_df (DataFrame): Contains currency and exchange_rate.
        stock_currency (str): The currency in which the stock is traded.

    Returns:
        DataFrame: A report containing price conversions in different currencies.

    Example:
        create_stock_currency_report(stock_df_long, exchange_rates_df, "USD")
        Returns:
            pd.DataFrame:
                ticker  price_type ticker_currency price currency exchange_rate currency_price
            0   AAPL    open       USD             150.0  EUR    0.85           127.5
            1   AAPL    high       USD             155.0  EUR    0.85           131.75
    """
    try:
        stock_df_long["ticker_currency"] = stock_currency.upper()

        merged_df = stock_df_long.merge(exchange_rates_df, how="cross")
        merged_df["currency_price"] = merged_df["price"] * merged_df["exchange_rate"]

        final_columns = ["date", "ticker", "price_type", "ticker_currency", "price", "currency", "exchange_rate", "currency_price"]
        final_df = merged_df[final_columns]

        logging.info(f"Successfully created the stock currency report for {stock_currency}.")
        return final_df

    except Exception as e:
        logging.exception(f"An error occurred while creating the stock currency report: {str(e)}")
        return None

def main():
    """Main function to execute the API data retrieval and processing flow."""
    """Main function to execute the API data retrieval and processing flow."""
    # Set up argument parser
    parser = argparse.ArgumentParser(description="Fetch stock data and currency exchange rates.")
    parser.add_argument("-t", "--ticker", type=str, required=True, help="Stock ticker symbol (e.g., AAPL)")
    parser.add_argument("-d", "--date", type=str, required=True, help="Date for fetching stock data (e.g., 2024-10-03)")
    parser.add_argument("-s", "--symbols", type=str, nargs='*', default=[],
                        help="List of symbols for exchange rate lookup")

    args = parser.parse_args()

    ticker = args.ticker
    date = args.date
    symbols = args.symbols
    try:
        # Step 1: Fetch stock data
        logging.info(f"Fetching stock data for {ticker} on {date}")
        stock_df = fetch_stock_data(ticker, date)
        if stock_df is None:
            logging.error(f"Failed to fetch stock data for {ticker}. Exiting.")
            return

        stock_df_long = create_price_types_df(stock_df)
        logging.info("Stock data reshaped successfully.")

        # Step 2: Fetch currency of the stock
        stock_currency = fetch_currency_name(ticker)
        if not stock_currency:
            logging.error(f"Could not fetch currency for {ticker}. Exiting.")
            return
        logging.info(f"Stock is traded in: {stock_currency.upper()}")

        # Step 3: Fetch all available currencies
        available_currencies = fetch_available_currencies()
        if available_currencies is None:
            logging.warning("Could not retrieve available currencies.")

        # Step 4: Fetch latest exchange rates
        exchange_rates_df = fetch_latest_currency_rates(stock_currency, symbols, date)
        if exchange_rates_df is None:
            logging.error("Failed to fetch exchange rates. Exiting.")
            return
        logging.info("Exchange rates retrieved successfully.")

        # Step 5: Create stock currency report
        df_stock_currency = create_stock_currency_report(stock_df_long, exchange_rates_df, stock_currency)
        logging.info("Stock currency report generated.")

        # Save report
        output_path = "/tmp/stock_currency_report.csv"
        df_stock_currency.to_csv(output_path, index=False)
        logging.info(f"Stock Currency Report saved to {output_path}")
        logging.info("You can upload this CSV file to GCS, S3, or any cloud storage.")

    except ValueError as e:
        logging.error(f"Error: {e}")

if __name__ == "__main__":
     main()


