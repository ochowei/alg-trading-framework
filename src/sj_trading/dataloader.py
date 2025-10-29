import backtrader as bt
import os
import pandas as pd
import yfinance as yf
from datetime import datetime


class Dataloader(bt.feeds.PandasData):
    """ 自定義 Backtrader 數據源，格式化永豐 API 和 yfinance 的數據 """
    params = (
        ('datetime', None),
        ('open', -1),
        ('high', -1),
        ('low', -1),
        ('close', -1),
        ('volume', -1),
        ('openinterest', -1),
    )


    @classmethod
    def from_yfinance(cls, symbol, start, end):
        """ 從 yfinance 下載歷史數據，並轉換為 Backtrader 可用格式 """
        df = yf.download(symbol, start=start, end=end)

       # 移除多餘的 "Ticker" 行，僅保留數據
        df.columns = df.columns.droplevel(1)  # 移除第二層標題 (Ticker)

        # 重新命名欄位，使其符合 Backtrader 的格式
        df = df.rename(columns={'Open': 'open', 'High': 'high', 'Low': 'low', 'Close': 'close', 'Volume': 'volume'})
        # df.index = df.index.tz_localize('America/New_York').tz_convert('Asia/Taipei')

        # 確保索引為日期格式
        df.index = pd.to_datetime(df.index)
        all_data = bt.feeds.PandasData(dataname=df)

        # 確保回傳時 dataname 傳入的是 DataFrame
        return all_data

    @classmethod
    def read_csv(cls, filename: str):
        if not os.path.exists(filename):
            print(f"Error: 檔案 {filename} 不存在。")
            return pd.DataFrame() # 回傳空的 DataFrame
        df = pd.read_csv(filename)
        return df
    
    @classmethod
    def list_tickers(self, df):
        tickers = df['Ticker'].unique()
        return tickers

    @classmethod
    def from_csv_df(self, df, symbol, start, end):

        df_bd = df[df['Ticker'] == symbol]
        r_df = df_bd[(df_bd['Date'] >= start) & (df_bd['Date'] <= end)].copy()
        r_df['Date'] = pd.to_datetime(r_df['Date'])
        r_df = r_df.rename(columns={'Open': 'open', 'High': 'high', 'Low': 'low', 'Close': 'close', 'Volume': 'volume'})
        r_df = r_df[['Date', 'open', 'high', 'low', 'close', 'volume']]
        r_df.set_index('Date', inplace=True)
        r_df.dropna(inplace=True)
        if r_df.empty:
            print(f"⚠️ {symbol} 在 {start} 至 {end} 之間沒有數據")
            return None
        all_data = bt.feeds.PandasData(dataname=r_df)
        # 確保回傳時 dataname 傳入的是 DataFrame
        return all_data

