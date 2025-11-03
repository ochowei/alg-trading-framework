import argparse
import json
from datetime import datetime
from pathlib import Path

import backtrader as bt
import pandas as pd

from sj_trading.commissions import TaiwanStockCommission
from sj_trading.config import Config
from sj_trading.dataloader import Dataloader
from sj_trading.strategies.bb_mr import BollingerBandsMeanReversion
from sj_trading.strategies.rsi_mr import RsiMeanReversion
from sj_trading.strategies.turtle import Turtle_v4_1


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
    start_date = Config.ONE_THOUSAND_DAYS_AGO.strftime('%Y-%m-%d')
    end_date = Config.ONE_WEEK_LATER.strftime('%Y-%m-%d')

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


def run_strategy_logic(data_file, input_file, output_file, start_date=None, end_date=None, skip_dates=None):
    """
    The core logic for running the strategy backtest.
    """
    # 1. 讀取參數檔案
    try:
        with open(input_file, 'r', encoding='utf-8') as f:
            params_data = json.load(f)
        params_map = {item['ticker']: item for item in params_data}
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"錯誤: 無法讀取或解析參數檔案 '{input_file}': {e}")
        return

    # 2. 讀取市場數據
    dataframe = Dataloader.read_csv(data_file)
    if dataframe.empty:
        print(f"錯誤: 無法從 '{data_file}' 讀取數據。")
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
            print(f"警告: 在 '{input_file}' 中找不到 {ticker} 的參數，已跳過。")
            continue

        config = params_map[ticker]
        strategy_name = config.get('strategy')
        parameters = config.get('parameters', {})

        if not strategy_name or not parameters:
            print(f"警告: {ticker} 的參數設定不完整，已跳過。")
            continue

        # 參數覆寫與轉換
        date_params = ['start_date', 'end_date']
        cli_dates = {'start_date': start_date, 'end_date': end_date}
        for p in date_params:
            # 優先使用 CLI 參數
            if cli_dates[p]:
                try:
                    parameters[p] = datetime.strptime(cli_dates[p], '%Y-%m-%d')
                except (ValueError, TypeError):
                    print(f"警告: CLI 的日期格式 '{cli_dates[p]}' 不正確，應為 YYYY-MM-DD。")
            # 否則，如果 JSON 中有字串，也進行轉換
            elif p in parameters and isinstance(parameters[p], str):
                try:
                    parameters[p] = datetime.strptime(parameters[p], '%Y-%m-%d')
                except (ValueError, TypeError):
                    print(f"警告: JSON 中的日期格式 '{parameters[p]}' 不正確，應為 YYYY-MM-DD。")

        if skip_dates:
            try:
                parameters['skip_dates'] = [datetime.strptime(d.strip(), '%Y-%m-%d').date() for d in
                                            skip_dates.split(',')]
            except ValueError:
                print(f"警告: skip_dates 的日期格式 '{skip_dates}' 不正確，應為 YYYY-MM-DD,YYYY-MM-DD。")
        elif 'skip_dates' in parameters and isinstance(parameters['skip_dates'], list):
            # 如果 JSON 中有 skip_dates, 轉換裡面的日期字串
            try:
                parameters['skip_dates'] = [datetime.strptime(d.strip(), '%Y-%m-%d').date() for d in
                                            parameters['skip_dates']]
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

        output_dir = Path(output_file).parent
        output_dir.mkdir(parents=True, exist_ok=True)

        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(all_trades, f, ensure_ascii=False, indent=2)

        print(f"✅ 策略執行完畢，共產生 {len(all_trades)} 筆交易訊號，已儲存至 {output_file}")
    else:
        print("所有策略執行完畢，但未產生任何交易訊號。")


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

    run_strategy_logic(
        data_file=args.data_file,
        input_file=args.input_file,
        output_file=args.output_file,
        start_date=args.start_date,
        end_date=args.end_date,
        skip_dates=args.skip_dates
    )
