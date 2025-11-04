import json
import os
from datetime import datetime, timedelta

import pandas as pd
import yfinance as yf

from sj_trading.config import Config


def download_data(start_date=None, end_date=None):
    """
    下載指定 Tickers 的歷史股價資料並存為 CSV。

    Args:
        start_date (str, optional): 開始日期 (YYYY-MM-DD)。預設為 1000 天前。
        end_date (str, optional): 結束日期 (YYYY-MM-DD)。預設為 7 天後。
    """
    # 如果未提供日期，則使用預設值
    if start_date is None:
        start_date = (datetime.now() - timedelta(days=1000)).strftime('%Y-%m-%d')
    if end_date is None:
        end_date = (datetime.now() + timedelta(days=7)).strftime('%Y-%m-%d')

    all_tickers = set()

    # 從 JSON 檔案讀取 Ticker
    try:
        with open('data/US_ticker_categories.json', 'r', encoding='utf-8') as f:
            ticker_categories = json.load(f)
            for category in ticker_categories.values():
                for ticker in category:
                    all_tickers.add(ticker)
    except FileNotFoundError:
        print("錯誤：`data/US_ticker_categories.json` 檔案不存在。")
        return
    except json.JSONDecodeError:
        print("錯誤：無法解析 `data/US_ticker_categories.json`。")
        return

    ticker_list = list(all_tickers)
    if not ticker_list:
        print("沒有找到任何 Ticker，下載中止。")
        return

    print(f"準備下載 {len(ticker_list)} 個 Ticker，日期範圍: {start_date} 至 {end_date}...")

    # 下載數據
    data = yf.download(
        tickers=ticker_list,
        start=start_date,
        end=end_date,
        group_by='ticker',
        auto_adjust=True,
        progress=True
    )

    # 處理並合併數據
    combined_df = pd.DataFrame()
    for ticker in ticker_list:
        if ticker in data and not data[ticker].empty:
            df = data[ticker].copy()
            df['Ticker'] = ticker
            df = df.reset_index()
            combined_df = pd.concat([combined_df, df], ignore_index=True)
        else:
            print(f"警告：未下載到 {ticker} 的資料。")

    # 儲存到 CSV
    base_name, extension = os.path.splitext(Config.YFINANCE_FILE_NAME)
    output_filename = f"{base_name}_{start_date}_{end_date}{extension}"
    combined_df.to_csv(output_filename, index=False)
    print(f"✅ 資料已成功儲存至 {output_filename}")


