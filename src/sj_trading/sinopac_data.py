import backtrader as bt
import shioaji as sj
import os
import pandas as pd
import yfinance as yf
from datetime import datetime

def login_sinopac():
    api = sj.Shioaji(simulation=True)
    api.login(
        api_key=os.environ["API_KEY"],
        secret_key=os.environ["SECRET_KEY"],
    )
    api.activate_ca(
        ca_path=os.environ["CA_CERT_PATH"],
        ca_passwd=os.environ["CA_PASSWORD"],
    )
    return api

api = login_sinopac()


class SinopacData(bt.feeds.PandasData):
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
    def from_sinopac(cls, symbol, start, end):
        """ 從永豐 API 下載歷史數據，並轉換為 Backtrader 可用格式 """
        kbars = api.kbars(api.Contracts.Stocks[symbol], start=start, end=end)
        df = pd.DataFrame({
            'datetime': pd.to_datetime(kbars.ts, unit='ns'),
            'open': kbars.Open,
            'high': kbars.High,
            'low': kbars.Low,
            'close': kbars.Close,
            'volume': kbars.Volume,
            'openinterest': 0,  # 永豐 API 不提供 Open Interest，因此填 0
        })
        df.set_index('datetime', inplace=True)

        df_daily = df.resample('1D').agg({
            'open': 'first',
            'high': 'max',
            'low': 'min',
            'close': 'last',
            'volume': 'sum',
            'openinterest': 'sum'
        }).dropna()
        print(df.tail(20))
        return cls(dataname=df_daily)

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
        print("timezone")
        print(df.index.tz)  # 輸出時區資訊

        # 確保回傳時 dataname 傳入的是 DataFrame
        return all_data

