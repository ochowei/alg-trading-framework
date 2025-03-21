import backtrader as bt
import shioaji as sj
import pandas as pd
import os
from datetime import datetime
from .turtle_strategy import (TurtleStrategy_v1_1, TurtleStrategy_v4_1,TurtleStrategy_v4_0, TurtleStrategy_v1_1_1)
from .taiwan_stock_commission import TaiwanStockCommission
from .sinopac_data import SinopacData
import yfinance as yf
from .logger import init_logger
import json

# 參數優化
def run_optimization_once(ticker:str, strategy:bt.Strategy, print_strat:bool=False, num_transactions:int=5):
    cerebro = bt.Cerebro(optreturn=False)
    # trace list: 0050, 2330, 0052, 元大全球 AI（00762）, 00737(國泰全球 AI), 00757(統一 FANG+ ETF)* 00635U.TW(期元大S&P黃金)*
    # 下載並載入數據
    data_1 = SinopacData.from_yfinance(symbol=ticker, start='2020-01-01', end='2025-12-31')
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
        TurtleStrategy_v4_1,
        stock_id=ticker,
        start_date=datetime(2023,1,1),
        entry_period=range(10, 50, 10),  # 測試 10, 20, 30, 40, 50 天突破
        exit_period=range(10, 41, 5)      # 測試 5, 10, 15, 20 天回撤
    )

       # 加入績效分析器
    cerebro.addanalyzer(bt.analyzers.SharpeRatio, _name='sharpe')
    cerebro.addanalyzer(bt.analyzers.DrawDown, _name='drawdown')
    cerebro.addanalyzer(bt.analyzers.TradeAnalyzer, _name='trade')
    cerebro.addanalyzer(bt.analyzers.Returns, _name='returns')  # 加入報酬率分析器
    cerebro.addanalyzer(bt.analyzers.Transactions, _name='transactions')
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

            # for asset, trade in trades.items():
            #     print(f"date: {date}, ")
            #     d = {
            #         "date": date,
            #         "symbol": asset,
            #         "size": trade[0],
            #         "price": trade[1],
            #         "commission": trade[2]
            #     }
            #     print(d)


        if print_strat:
            print(f"\n=== 策略參數: entry={strat.params.entry_period}, exit={strat.params.exit_period} ===")
            print(f"Sharpe Ratio: {sharpe:.3f}" if sharpe else "Sharpe Ratio: 無法計算")
            print(f"Max Drawdown: {max_drawdown:.2f}%")
            print(f"Win Rate: {win_rate:.2%}")
            print(f"Profit Factor: {profit_factor:.2f}")
            print(f"Cumulative Return: {cumulative_return:.2%}" if cumulative_return is not None else "Cumulative Return: 無法計算")
        

        # 確保 Sharpe Ratio 有效
        if sharpe is not None and sharpe > best_sharpe:
            best_sharpe = sharpe
            best_result = {
                "params": strat.params,
                "sharpe": sharpe,
                "max_drawdown": max_drawdown,
                "win_rate": win_rate,
                "profit_factor": profit_factor,
                "cumulative_return": cumulative_return,
                "strat": strat
            }

    # 顯示最佳策略結果
    if best_result is not None and best_sharpe != -float('inf'):
        print("\n=== 最佳策略 (根據 Sharpe Ratio) ===")
        print(f"Entry Period: {best_result["params"].entry_period}")
        print(f"Exit Period: {best_result["params"].exit_period}")
        print(f"Sharpe Ratio: {best_result['sharpe']:.3f}")
        print(f"Max Drawdown: {best_result['max_drawdown']:.2f}%")
        print(f"Win Rate: {best_result['win_rate']:.2%}")
        print(f"Profit Factor: {best_result['profit_factor']:.2f}")     
        print(f"Cumulative Return: {best_result['cumulative_return']:.2%}")   
        print(f"Best Sharpe Ratio: {best_sharpe:.3f}")
        
        strat = best_result["strat"]
        transactions = strat.analyzers.transactions.get_analysis()

        # 轉換交易紀錄為 DataFrame
        df_trades = []
        # print last x trades
        x = num_transactions
        for date, trades in list(transactions.items())[-x:]:
            for trade in trades:
                d = {
                    "date": f"{date}",
                    "size": trade[0],
                    "price": trade[1],
                    "total": trade[4]
                }
                df_trades.append(d)
        
        df_trades = pd.DataFrame(df_trades)
        print(f"\n=== 最後 {x} 筆交易 ===")
        print(df_trades)
       
        
    else:
        print("\n⚠️ 無法找到最佳策略，可能是所有策略的 Sharpe Ratio 無法計算。")
    
    # 優化結束
    print(f"結束優化 {ticker} 的策略參數")
    # cerebro.plot()

def run_optimization():
    # tutle 4.1 trace list: 0050.TW, 2330.TW, 00757, 00635U.TW,     
    
    ticker_list_1 = ['00757.TW'] # 第一關注目標
    ticker_list_2 = ['0050.TW', '2330.TW', '00737.TW', '00635U.TW'] # 第二關注目標

    logger = init_logger()
    target_list = ticker_list_1
    
    # read json from ./data/ETF.json with utf-8
    etf_codes = []

    with open('data/ETF.json', 'r', encoding='utf-8') as f:
        data = json.load(f)
        for etf in data:
            code = etf["基金代號"]
            # concat code with .TW
            etf_codes.append(f"{code}.TW")
            
    # print(f"目標清單: {target_list}")
    target_list = etf_codes
    error_targets = []

    for ticker in target_list:
        print(f"開始優化 {ticker} 的策略參數")
        try:
            run_optimization_once(ticker, TurtleStrategy_v4_1, False, 5)
        except Exception as e:
            print(e)
            print(f"優化 {ticker} 的策略參數時發生錯誤: {e}")
            error_targets.append({ticker: str(e)})
    print(f"優化結束，發生錯誤的清單: {error_targets}")
            

