import backtrader as bt
import shioaji as sj
import pandas as pd
import os
from datetime import datetime
from .turtle_strategy import (TurtleStrategy_v1_1, TurtleStrategy_v4_0, TurtleStrategy_v1_1_1)
from .taiwan_stock_commission import TaiwanStockCommission
from .sinopac_data import SinopacData
import yfinance as yf

# 設定 Shioaji 連線


def my_test():
    cerebro = bt.Cerebro(optreturn=False)
    ticker = '00757.TW'
    # trace list: 0050, 2330, 0052, 元大全球 AI（00762）, 00737(國泰全球 AI), 00757(統一 FANG+ ETF)*
    # 下載並載入數據
    data_1 = SinopacData.from_yfinance(symbol=ticker, start='2022-01-01', end='2025-12-31')
    # stock = yf.Ticker(ticker)

    # # 嘗試獲取不同名稱
    # long_name = stock.info.get("longName", "N/A")
    # short_name = stock.info.get("shortName", "N/A")

    # print(f"股票代號: {ticker}")
    # print(f"公司名稱（longName）: {long_name}")
    # print(f"公司名稱（shortName）: {short_name}")
    cerebro.adddata(data_1)

    cerebro.broker.setcash(100000)
    cerebro.broker.addcommissioninfo(TaiwanStockCommission())

    print('Starting Portfolio Value: %.2f' % cerebro.broker.getvalue())
    cerebro.optstrategy(
        TurtleStrategy_v1_1_1,
        start_date=datetime(2024,7,1),
        entry_period=range(10, 31, 10),  # 測試 10, 20, 30, 40, 50 天突破
        exit_period=range(10, 21, 5)      # 測試 5, 10, 15, 20 天回撤
    )

       # 加入績效分析器
    cerebro.addanalyzer(bt.analyzers.SharpeRatio, _name='sharpe')
    cerebro.addanalyzer(bt.analyzers.DrawDown, _name='drawdown')
    cerebro.addanalyzer(bt.analyzers.TradeAnalyzer, _name='trade')
    cerebro.addanalyzer(bt.analyzers.Returns, _name='returns')  # 加入報酬率分析器

    # cerebro.addstrategy(TurtleStrategy_v1_1_1)
    optimized_results = cerebro.run(maxcpus=1)
    # print('Ending Portfolio Value: %.2f' % cerebro.broker.getvalue())
    # 遍歷所有優化組合並顯示績效
    best_sharpe = -float('inf')
    best_result = None

    for result in optimized_results:
        strat = result[0]  # 取回測結果中的策略

        # 取得績效數據，加入錯誤處理
        try:
            sharpe = strat.analyzers.sharpe.get_analysis().get('sharperatio', None)
        except Exception as e:
            sharpe = None
            print(f"Sharpe Ratio 計算錯誤: {e}")

        max_drawdown = strat.analyzers.drawdown.get_analysis()["max"]["drawdown"]
        trade_analysis = strat.analyzers.trade.get_analysis()
        cumulative_return = strat.analyzers.returns.get_analysis().get("rtot", None)  # 取得累積報酬率

        win_rate = trade_analysis["won"]["total"] / trade_analysis["total"]["total"] if trade_analysis["total"]["total"] > 0 else 0
        profit_factor = (trade_analysis["won"]["pnl"]["total"] / abs(trade_analysis["lost"]["pnl"]["total"])) if trade_analysis["lost"]["pnl"]["total"] != 0 else float('inf')

        print(f"\n=== 策略參數: entry={strat.params.entry_period}, exit={strat.params.exit_period} ===")
        print(f"Sharpe Ratio: {sharpe:.3f}" if sharpe else "Sharpe Ratio: 無法計算")
        print(f"Max Drawdown: {max_drawdown:.2f}%")
        print(f"Win Rate: {win_rate:.2%}")
        print(f"Profit Factor: {profit_factor:.2f}")
        print(f"Cumulative Return: {cumulative_return:.2%}" if cumulative_return is not None else "Cumulative Return: 無法計算")
        final_value = cerebro.broker.getvalue()
        print(f"Final Portfolio Value: {final_value:.2f}")


        # 確保 Sharpe Ratio 有效
        if sharpe is not None and sharpe > best_sharpe:
            best_sharpe = sharpe
            best_result = strat

    # 顯示最佳策略結果
    if best_result is not None and best_sharpe != -float('inf'):
        print("\n=== 最佳策略 (根據 Sharpe Ratio) ===")
        print(f"Entry Period: {best_result.params.entry_period}")
        print(f"Exit Period: {best_result.params.exit_period}")
        print(f"Best Sharpe Ratio: {best_sharpe:.3f}")
    else:
        print("\n⚠️ 無法找到最佳策略，可能是所有策略的 Sharpe Ratio 無法計算。")
    # cerebro.plot()
