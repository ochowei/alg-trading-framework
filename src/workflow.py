import argparse
import backtrader as bt
import shioaji as sj
import pandas as pd
import os
from datetime import datetime
import yfinance as yf
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
def run_optimization_once(df:pd.DataFrame, ticker:str, strategy:bt.Strategy, print_strat:bool=False, num_transactions:int=5, performance_target:str=Config.PERFORMANCE_TARGET, opt_args=Config.OPT_PARAMETERS_TUTLE_4_1):
    cerebro = bt.Cerebro(optreturn=False)
    # trace list: 0050, 2330, 0052, 元大全球 AI（00762）, 00737(國泰全球 AI), 00757(統一 FANG+ ETF)* 00635U.TW(期元大S&P黃金)*
    # 下載並載入數據
    start = Config.ONE_THOUSAND_DAYS_AGO.strftime('%Y-%m-%d')
    end = Config.ONE_WEEK_LATER.strftime('%Y-%m-%d')
    # end = one_week_later.strftime('%Y-%m-%d')
    print(f"start: {start}, end: {end}")

    data_1 = Dataloader.from_csv_df(df=df, symbol=ticker, start=Config.ONE_THOUSAND_DAYS_AGO.strftime('%Y-%m-%d'), end=end)
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
                "strat": strat
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

import argparse

def opt_strategy(filename: str = Config.YFINANCE_FILE_NAME):
    dataframe =  Dataloader.read_csv(filename)
    if dataframe.empty:
        print(f"無法從 {filename} 讀取到數據，lookup_target 中止。")
        return
    # tutle 4.1 trace list: 0050.TW, 2330.TW, 00757, 00635U.TW, 00893.TW, 00895.TW
    ticker_list_1 = ['00893.TW'] # 第一關注目標
    ticker_list_2 = ['0050.TW', '2330.TW', '00737.TW', '00635U.TW'] # 第二關注目標
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
            best_result = run_optimization_once(dataframe, ticker, opt_strategy, False, num_transactions, "annual_return", opt_args=opt_args)
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
                "parameters": params
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
    for x in watch_list:
        print_backtest_result(level=logging.INFO, bt_result=x["bt_result"], num_transactions=5)

def check_target():
    logger = init_logger("backtrader.log")
    dataframe =  Dataloader.read_csv()

    target_list = Config.WATCH_TARGETS
    opt_args = Config.OPT_PARAMETERS_BB_MR

    opt_strategy = BollingerBandsMeanReversion

    num_transactions = 5
    errors = []
    result_list = []
    for ticker in target_list:
        print(f"開始優化 {ticker} 的策略參數")
        best_result = None
        try:
            best_result = run_optimization_once(dataframe, ticker, opt_strategy, False, num_transactions, "annual_return", opt_args)
        except Exception as e:
            print(f"⚠️ 優化 {ticker} 時發生錯誤: {e}")
            logger.error(f"⚠️ 優化 {ticker} 時發生錯誤: {e}")
            errors.append({"ticker": ticker, "error": str(e)})
            continue
        if best_result is not None and best_result['sharpe'] != -float('inf'):
            sharpe = best_result["sharpe"]
         

            print_backtest_result(level=logging.DEBUG, bt_result=best_result, num_transactions=5, filename=f"{ticker}/tutle_strategy.log")
       

            df_trades = []
        # print last x trades
            strat = best_result["strat"]                 
                    
            df_trades = pd.DataFrame(strat.signal_list)
            max_trade_date = df_trades['date'].max()
            #check if max_trade_date is greater than 2025-03-22
            #if ( df_trades['action'].iloc[-1] == -1 ):
                #and max_trade_date > five_days_ago_str
            result_list.append({"ticker": ticker, "bt_result": best_result})

        print(f"結束優化 {ticker} 的策略參數")

    print("🎉 優化完成！")
    for x in result_list:
        print_backtest_result(level=logging.INFO, bt_result=x["bt_result"], num_transactions=5)

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


def download_data_cli():
    """
    為 download_data 提供命令列介面。
    """
    parser = argparse.ArgumentParser(description="下載 yfinance 股價資料")
    parser.add_argument(
        "--start-date",
        type=str,
        default=None,
        help="下載開始日期 (格式: YYYY-MM-DD)。預設為 1000 天前。"
    )
    parser.add_argument(
        "--end-date",
        type=str,
        default=None,
        help="下載結束日期 (格式: YYYY-MM-DD)。預設為 7 天後。"
    )
    args = parser.parse_args()

    # 驗證日期格式
    for date_str in [args.start_date, args.end_date]:
        if date_str:
            try:
                datetime.strptime(date_str, '%Y-%m-%d')
            except ValueError:
                parser.error(f"日期格式錯誤: {date_str}。請使用 YYYY-MM-DD 格式。")

    download_data(start_date=args.start_date, end_date=args.end_date)

def main():
    """
    主執行入口點，用於解析命令列參數並執行 lookup_target。
    """
    parser = argparse.ArgumentParser(description="演算法交易框架 - 策略回測優化")

    parser.add_argument(
        "--filename",
        type=str,
        default=Config.YFINANCE_FILE_NAME,
        help=f"要讀取的 CSV 資料檔案路徑 (預設: {Config.YFINANCE_FILE_NAME})"
    )

    args = parser.parse_args()

    print(f"🔄 開始執行 lookup_target，使用資料檔案: {args.filename}")

    opt_strategy(filename=args.filename)




def run_strategy_once(df: pd.DataFrame, ticker: str, strategy_class: bt.Strategy, strategy_params: dict):
    """
    執行單次回測，不進行優化。

    Args:
        df (pd.DataFrame): 包含所有股票數據的 DataFrame。
        ticker (str): 要回測的股票代號。
        strategy_class (bt.Strategy): 要使用的策略類別。
        strategy_params (dict): 策略的參數。

    Returns:
        list: 交易訊號列表 (signal_list)。
    """
    cerebro = bt.Cerebro()

    # 從參數中獲取日期，若無則使用預設值
    start_date =  Config.ONE_THOUSAND_DAYS_AGO.strftime('%Y-%m-%d')
    end_date =  Config.ONE_WEEK_LATER.strftime('%Y-%m-%d')

    # 載入數據
    data = Dataloader.from_csv_df(df=df, symbol=ticker, start=start_date, end=end_date)
    if data is None:
        print(f"警告: {ticker} 沒有足夠的數據，跳過回測。")
        return []

    cerebro.adddata(data)

    # 設定初始資金和佣金
    cerebro.broker.setcash(100000)
    cerebro.broker.addcommissioninfo(TaiwanStockCommission())

    # 加入策略 (非優化)
    cerebro.addstrategy(strategy_class, **strategy_params)

    # 加入分析器以提取交易訊號
    # 確保策略內部有 self.signal_list
    cerebro.addanalyzer(bt.analyzers.TradeAnalyzer, _name='trade')

    # 執行回測
    results = cerebro.run()
    strat = results[0]

    # 從策略實例中提取 signal_list
    if hasattr(strat, 'signal_list'):
        return strat.signal_list
    else:
        print(f"警告: 策略 {strategy_class.__name__} 沒有 'signal_list' 屬性。")
        return []



def run_strategy_cli():
    """
    CLI 進入點，用於根據儲存的最佳參數重新執行策略。
    """
    parser = argparse.ArgumentParser(description="使用最佳化後的參數執行單次回測，並產生交易訊號。")
    parser.add_argument(
        "--data-file",
        type=str,
        default=Config.YFINANCE_FILE_NAME,
        help=f"包含市場數據的 CSV 檔案 (預設: {Config.YFINANCE_FILE_NAME})"
    )
    parser.add_argument(
        "--input-file",
        type=str,
        default="output/best_strategy_params.json",
        help="包含最佳策略參數的 JSON 檔案 (預設: output/best_strategy_params.json)"
    )
    parser.add_argument(
        "--output-file",
        type=str,
        default="output/strategy_trades.json",
        help="儲存交易訊號的輸出 JSON 檔案 (預設: output/strategy_trades.json)"
    )
    parser.add_argument("--start-date", type=str, help="覆寫所有策略的開始日期 (YYYY-MM-DD)。")
    parser.add_argument("--end-date", type=str, help="覆寫所有策略的結束日期 (YYYY-MM-DD)。")
    parser.add_argument("--skip-dates", type=str, help="覆寫所有策略要跳過的日期 (YYYY-MM-DD,YYYY-MM-DD)。")

    args = parser.parse_args()

    # 1. 讀取參數檔案
    try:
        with open(args.input_file, 'r', encoding='utf-8') as f:
            params_data = json.load(f)
        params_map = {item['ticker']: item for item in params_data}
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"錯誤: 無法讀取或解析參數檔案 '{args.input_file}': {e}")
        return

    # 2. 讀取市場數據
    dataframe = Dataloader.read_csv(args.data_file)
    if dataframe.empty:
        print(f"錯誤: 無法從 '{args.data_file}' 讀取數據。")
        return

    # 3. 獲取 Ticker 列表
    tickers = Dataloader.list_tickers(dataframe)
    target_list = tickers
    all_trades = []

    # 4. 策略對應表
    strategy_map = {
        "BollingerBandsMeanReversion": BollingerBandsMeanReversion,
        "Turtle_v4_1": Turtle_v4_1,
        "RsiMeanReversion": RsiMeanReversion
    }

    # 5. 遍歷 Ticker 並執行策略
    for ticker in target_list:
        if ticker not in params_map:
            print(f"警告: 在 '{args.input_file}' 中找不到 {ticker} 的參數，已跳過。")
            continue

        config = params_map[ticker]
        strategy_name = config.get('strategy')
        parameters = config.get('parameters', {})

        if not strategy_name or not parameters:
            print(f"警告: {ticker} 的參數設定不完整，已跳過。")
            continue

        # 參數覆寫與轉換
        date_params = ['start_date', 'end_date']
        for p in date_params:
            # 優先使用 CLI 參數
            if getattr(args, p):
                try:
                    parameters[p] = datetime.strptime(getattr(args, p), '%Y-%m-%d')
                except (ValueError, TypeError):
                    print(f"警告: CLI 的日期格式 '{getattr(args, p)}' 不正確，應為 YYYY-MM-DD。")
            # 否則，如果 JSON 中有字串，也進行轉換
            elif p in parameters and isinstance(parameters[p], str):
                 try:
                    parameters[p] = datetime.strptime(parameters[p], '%Y-%m-%d')
                 except (ValueError, TypeError):
                    print(f"警告: JSON 中的日期格式 '{parameters[p]}' 不正確，應為 YYYY-MM-DD。")


        if args.skip_dates:
            try:
                parameters['skip_dates'] = [datetime.strptime(d.strip(), '%Y-%m-%d').date() for d in args.skip_dates.split(',')]
            except ValueError:
                 print(f"警告: skip_dates 的日期格式 '{args.skip_dates}' 不正確，應為 YYYY-MM-DD,YYYY-MM-DD。")
        elif 'skip_dates' in parameters and isinstance(parameters['skip_dates'], list):
             # 如果 JSON 中有 skip_dates, 轉換裡面的日期字串
             try:
                parameters['skip_dates'] = [datetime.strptime(d.strip(), '%Y-%m-%d').date() for d in parameters['skip_dates']]
             except (ValueError, TypeError):
                print(f"警告: JSON 中的 skip_dates 包含不正確的日期格式。")

        strategy_class = strategy_map.get(strategy_name)
        if not strategy_class:
            print(f"警告: 找不到名為 '{strategy_name}' 的策略，已跳過 {ticker}。")
            continue

        print(f"正在為 {ticker} 執行策略: {strategy_name}...")

        # 呼叫 `run_strategy_once`
        signal_list = run_strategy_once(dataframe, ticker, strategy_class, parameters)

        if signal_list:
            # 將 ticker 加入每個交易訊號中
            for trade in signal_list:
                trade['ticker'] = ticker
            all_trades.extend(signal_list)

    # 6. 排序並儲存結果
    if all_trades:
        all_trades.sort(key=lambda x: x['date'])

        output_dir = Path(args.output_file).parent
        output_dir.mkdir(parents=True, exist_ok=True)

        with open(args.output_file, 'w', encoding='utf-8') as f:
            json.dump(all_trades, f, ensure_ascii=False, indent=2)

        print(f"✅ 策略執行完畢，共產生 {len(all_trades)} 筆交易訊號，已儲存至 {args.output_file}")
    else:
        print("所有策略執行完畢，但未產生任何交易訊號。")


if __name__ == "__main__":
    main()
