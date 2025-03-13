import backtrader as bt
import shioaji as sj
import pandas as pd
import os
from datetime import datetime
from .turtle_strategy import (TurtleStrategy_v1_1, TurtleStrategy_v4_0, TurtleStrategy_v1_1_1)
from .taiwan_stock_commission import TaiwanStockCommission
from .sinopac_data import SinopacData

# 設定 Shioaji 連線


def my_test():
    cerebro = bt.Cerebro(optreturn=False)

    # trace list: 0050, 2330, 0052
    # 下載並載入數據
    data_1 = SinopacData.from_yfinance(symbol='0050.TW', start='2022-01-01', end='2025-12-31')
    cerebro.adddata(data_1)

    cerebro.broker.setcash(100000)
    cerebro.broker.addcommissioninfo(TaiwanStockCommission())

    print('Starting Portfolio Value: %.2f' % cerebro.broker.getvalue())
    cerebro.optstrategy(
        TurtleStrategy_v1_1_1,
        start_date=datetime(2024,5,1),
        entry_period=range(10, 31, 10),  # 測試 10, 20, 30, 40, 50 天突破
        exit_period=range(10, 21, 5)      # 測試 5, 10, 15, 20 天回撤
    )
    # cerebro.addstrategy(TurtleStrategy_v1_1_1)
    optimized_results = cerebro.run(maxcpus=1)
    # print('Ending Portfolio Value: %.2f' % cerebro.broker.getvalue())

    # cerebro.plot()
