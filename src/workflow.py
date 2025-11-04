import backtrader as bt
import pandas as pd
from datetime import datetime
import json
import numpy as np
import logging
from datetime import datetime, timedelta
from pathlib import Path

from sj_trading.dataloader import Dataloader
from sj_trading.config import Config


from sj_trading.strategies.turtle import Turtle_v4_1, Turtle_v4_1_1
from sj_trading.strategies.rsi_mr import RsiMeanReversion
from sj_trading.strategies.bb_mr import BollingerBandsMeanReversion
from sj_trading.analyzers import HoldingPeriodAnalyzer
from sj_trading.commissions import TaiwanStockCommission


# 參數優化
def run_optimization_ticker(
    df: pd.DataFrame,
    ticker: str,
    strategy: bt.Strategy,
    start_date: str,
    end_date: str,
    print_strat: bool = False,
    num_transactions: int = 5,
    performance_target: str = Config.PERFORMANCE_TARGET,
    opt_args=Config.OPT_PARAMETERS_TUTLE_4_1
):
    cerebro = bt.Cerebro(optreturn=False)
    # 下載並載入數據
    print(f"start: {start_date}, end: {end_date}")

    data_1 = Dataloader.from_csv_df(df=df, symbol=ticker, start=start_date, end=end_date)
    # stock = yf.Ticker(ticker)
    # check if data_1 is Less than 1
    if data_1 is None:
        print(f"股票代號: {ticker} 沒有數據")
        return

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
        strategy,
        stock_id=ticker,
        **opt_args
    )


       # 加入績效分析器
    cerebro.addanalyzer(bt.analyzers.SharpeRatio,
                        _name='sharpe',
                        timeframe=bt.TimeFrame.Days,
                        riskfreerate=0.01) # 假設 1% (0.01) 的無風險利率
    cerebro.addanalyzer(bt.analyzers.DrawDown, _name='drawdown')
    cerebro.addanalyzer(bt.analyzers.TradeAnalyzer, _name='trade')
    cerebro.addanalyzer(bt.analyzers.Transactions, _name='transactions')
    cerebro.addanalyzer(HoldingPeriodAnalyzer, _name='holdings')
    cerebro.addanalyzer(bt.analyzers.TimeReturn, _name='timereturn')
    # cerebro.addstrategy(TurtleStrategy_v1_1_1)
    optimized_results = cerebro.run(maxcpus=1, optreturn=False)
    # print('Ending Portfolio Value: %.2f' % cerebro.broker.getvalue())
    # 遍歷所有優化組合並顯示績效
    logger = init_logger(f"{ticker}/tutle_strategy.log")

    best_performance = -float('inf')
    best_result = None

    for result in optimized_results:
        strat = result[0]  # 取回測結果中的策略

        # 取得績效數據，加入錯誤處理
        try:
            sharpe = strat.analyzers.sharpe.get_analysis().get('sharperatio', None)
        except Exception as e:
            sharpe = None
            print(f"Sharpe Ratio 計算錯誤: {e}")
            continue

        max_drawdown = strat.analyzers.drawdown.get_analysis()["max"]["drawdown"]
        trade_analysis = strat.analyzers.trade.get_analysis()

        # win_rate = trade_analysis["won"]["total"] / trade_analysis["total"]["total"] if trade_analysis["total"]["total"] > 0 else 0
        # profit_factor = (trade_analysis["won"]["pnl"]["total"] / abs(trade_analysis["lost"]["pnl"]["total"])) if trade_analysis["lost"]["pnl"]["total"] != 0 else float('inf')
        # 安全地抓出獲利、虧損、總交易數
        won_pnl = trade_analysis.get('won', {}).get('pnl', {}).get('total', 0)
        lost_pnl = abs(trade_analysis.get('lost', {}).get('pnl', {}).get('total', 0))
        total_trades = trade_analysis.get('total', {}).get('total', 0)
        won_trades = trade_analysis.get('won', {}).get('total', 0)
        holding_stats = strat.analyzers.holdings.get_analysis()
        # 計算 Profit Factor
        profit_factor = (won_pnl / lost_pnl) if lost_pnl != 0 else float('inf')

        returns = pd.Series(strat.analyzers.timereturn.get_analysis())
        cumulative_return_series = (1 + returns).cumprod()
        cumulative_return = cumulative_return_series.iloc[-1] - 1

        days = (returns.index[-1] - returns.index[0]).days
        years = days / 365  # 或用 252 換算為交易年也可以，但這樣更精準

        # 年化報酬率（compound annual growth rate, CAGR）
        annualized_return = (1 + cumulative_return) ** (1 / years) - 1

        # 計算 Win Rate（勝率）
        win_rate = (won_trades / total_trades) if total_trades > 0 else 0

        performance = {
            "sharpe": sharpe,
            "max_drawdown": max_drawdown,
            "win_rate": win_rate,
            "profit_factor": profit_factor,
            "cumulative_return": cumulative_return,
            "annual_return": annualized_return
        }

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


        params_dict = strat.params._getkwargs()
        
        logger = init_logger(f"{ticker}/tutle_strategy.log", mode='a')            
        
        logger.debug("===================")
        
        logger.debug(params_dict)

        logger.debug(f"Sharpe Ratio: {sharpe:.3f}" if sharpe else "Sharpe Ratio: 無法計算")
            
        logger.debug(f"Max Drawdown: {max_drawdown:.2f}%")
            
        logger.debug(f"Win Rate: {win_rate:.2%}")
            
        logger.debug(f"Profit Factor: {profit_factor:.2f}")
            
        logger.debug(f"Cumulative Return: {cumulative_return:.2%}" if cumulative_return is not None else "Cumulative Return: 無法計算")

        logger.debug(f"Annual Return: {annualized_return:.2%}" if annualized_return is not None else "Annual Return: 無法計算")

        logger.debug(f"交易筆數：{holding_stats['count']}")
        logger.debug(f"平均持有時間：{holding_stats['average_bars']:.2f} bars, {holding_stats['average_days']:.2f} 天")
        logger.debug(f"總共持有時間：{sum(holding_stats['holding_days']) }  天")
        start_value = cerebro.broker.startingcash
        logger.debug(f"總資產: {start_value*(cumulative_return+1)}")
        
        compare_target = performance[performance_target]
        # 確保 Sharpe Ratio 有效
        if sharpe is not None and compare_target > best_performance:
            best_performance = compare_target
            best_result = {
                "params": strat.params,
                "sharpe": sharpe,
                "max_drawdown": max_drawdown,
                "win_rate": win_rate,
                "profit_factor": profit_factor,
                "cumulative_return": cumulative_return,
                "annual_return": annualized_return,
                "strat": strat,
                "sum_holding_days": sum(holding_stats['holding_days']),
                "num_trades": total_trades,
                "average_holding_days": holding_stats['average_bars']
            }
        


    # 顯示最佳策略結果
    if best_result is not None and best_performance != -float('inf'):
        
        return best_result
       
        
    else:
        print("\n⚠️ 無法找到最佳策略，可能是所有策略的 Sharpe Ratio 無法計算。")
        return None
    
    
    # cerebro.plot()

from sj_trading.logger import init_logger

def print_backtest_result(bt_result, num_transactions: int, level=logging.INFO, filename="backtrader.log"):
    strat = bt_result["strat"]
    transactions = strat.analyzers.transactions.get_analysis()
    stock_id = strat.params.stock_id
    logger = init_logger(filename)
    # 轉換交易紀錄為 DataFrame
    df_trades = []
    # print last x trades
    
    for date, trades in list(transactions.items())[-num_transactions:]:
        for trade in trades:
            d = {
                "date": f"{date}",
                "size": trade[0],
                "price": trade[1],
                "total": trade[4]
            }
            df_trades.append(d)
    
    df_trades = pd.DataFrame(df_trades)

    annual_return = bt_result["annual_return"]
    sharpe = bt_result["sharpe"]
    # print(f"\n=== 最後 {num_transactions} 筆交易 ===")
    # print(df_trades)       
    # print(f"Entry Period: {bt_result["params"].entry_period}")
    # print(f"Exit Period: {bt_result["params"].exit_period}")
    # print(f"Sharpe Ratio: {sharpe:.3f}")
    # print(f"Max Drawdown: {bt_result['max_drawdown']:.2f}%")
    # print(f"Win Rate: {bt_result['win_rate']:.2%}")
    # print(f"Profit Factor: {bt_result['profit_factor']:.2f}")     
    # print(f"Cumulative Return: {bt_result['cumulative_return']:.2%}") 
    # print(f"Annual Return: {annual_return:.2%}")
    #     

    params_dict = strat.params._getkwargs()
    logger.log(level,f"==========================")
    logger.log(level,f"Stock ID: {stock_id}")
    logger.log(level,f"{params_dict}")
    logger.log(level,f"Sharpe Ratio: {sharpe:.3f}")
    logger.log(level,f"Max Drawdown: {bt_result['max_drawdown']:.2f}%")
    logger.log(level,f"Win Rate: {bt_result['win_rate']:.2%}")
    logger.log(level,f"Profit Factor: {bt_result['profit_factor']:.2f}")
    logger.log(level,f"Cumulative Return: {bt_result['cumulative_return']:.2%}")
    logger.log(level,f"Annual Return: {annual_return:.2%}")

def opt_strategy(filename: str = Config.YFINANCE_FILE_NAME, start_date: str = None, end_date: str = None):
    dataframe =  Dataloader.read_csv(filename)
    if dataframe.empty:
        print(f"無法從 {filename} 讀取到數據，opt_strategy 中止。")
        return
  
    tickers = Dataloader.list_tickers(dataframe)
    logger = init_logger("backtrader.log")
    target_list = tickers
    
    opt_args = Config.OPT_PARAMETERS_BB_MR

    opt_strategy = BollingerBandsMeanReversion

    # read json from ./data/ETF.json with utf-8           
    # print(f"目標清單: {target_list}")
    num_transactions = 5
    errors = []
    watch_list = []
    all_best_trades = []
    all_best_params = []
    
    for ticker in target_list:
        print(f"開始優化 {ticker} 的策略參數")
        best_result = None
        try:
            best_result = run_optimization_ticker(
                df=dataframe,
                ticker=ticker,
                strategy=opt_strategy,
                start_date=start_date,
                end_date=end_date,
                opt_args=opt_args
            )
        except Exception as e:
            print(f"⚠️ 優化 {ticker} 時發生錯誤: {e}")
            logger.error(f"⚠️ 優化 {ticker} 時發生錯誤: {e}")
            errors.append({"ticker": ticker, "error": str(e)})
            continue
        if best_result is not None and best_result['sharpe'] != -float('inf'):
            sharpe = best_result["sharpe"]
            win_rate = best_result["win_rate"]
            cumulative_return = best_result["cumulative_return"]
            if (sharpe < 0 ):
                continue

            print_backtest_result(level=logging.DEBUG, bt_result=best_result, num_transactions=5, filename=f"{ticker}/tutle_strategy.log")

            if cumulative_return <= 0:
                continue

            # 提取參數並處理 datetime
            params = best_result["strat"].params._getkwargs()
            for key, value in params.items():
                if isinstance(value, datetime):
                    params[key] = value.isoformat()

            # 儲存最佳參數
            all_best_params.append({
                "ticker": ticker,
                "strategy": opt_strategy.__name__,
                "parameters": params,
                "sharpe": sharpe,
                "max_drawdown": best_result["max_drawdown"],
                "win_rate": win_rate,
                "cumulative_return": cumulative_return,
                "sum_holding_days": best_result["sum_holding_days"],
                "num_trades": best_result["num_trades"],
                "average_holding_days":  best_result["average_holding_days"]
                
            })

            strat = best_result["strat"]
            if strat.signal_list:
                trades = strat.signal_list
                for trade in trades:
                    trade["ticker"] = ticker
                all_best_trades.extend(trades)

            df_trades = pd.DataFrame(strat.signal_list)
            if not df_trades.empty:
                max_trade_date = df_trades['date'].max()
                #check if max_trade_date is greater than 2025-03-22
                if ( df_trades['action'].iloc[-1]==1 and max_trade_date > Config.FIVE_DAYS_AGO_STR):
                    watch_list.append({"ticker": ticker, "bt_result": best_result})

        print(f"結束優化 {ticker} 的策略參數")

    # Sort all trades by date
    all_best_trades.sort(key=lambda x: x['date'])

    # Ensure the output directory exists
    output_dir = Path("output")
    output_dir.mkdir(exist_ok=True)

    # Write to JSON file
    output_file = output_dir / "best_strategy_trades.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(all_best_trades, f, ensure_ascii=False, indent=2)
    
    print(f"✅ 最佳策略的交易紀錄已匯出至 {output_file}")

    # Write params to JSON file
    params_output_file = output_dir / "best_strategy_params.json"
    with open(params_output_file, 'w', encoding='utf-8') as f:
        json.dump(all_best_params, f, ensure_ascii=False, indent=2)
    print(f"✅ 最佳策略的參數已匯出至 {params_output_file}")
    sum_of_pnl = 0
    for x in all_best_trades:
        if 'pnl' in x:
            sum_of_pnl += x['pnl']
    print(f"所有最佳策略交易的總 PnL: {sum_of_pnl:.2f}")

    if len(errors) > 0:
        print("\n=== 錯誤清單 ===")
        for error in errors:
            print(f"股票代號: {error['ticker']}, 錯誤: {error['error']}")
    print("🎉 優化完成！")
    # for x in watch_list:
    #     print_backtest_result(level=logging.INFO, bt_result=x["bt_result"], num_transactions=5)
