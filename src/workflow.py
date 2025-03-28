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

class ARGS:
    """存放所有預定義的參數和常量"""
    
    # 日期相關變數
    FIVE_DAYS_AGO_STR = (datetime.now() - timedelta(days=5)).strftime('%Y-%m-%d')
    ONE_WEEK_LATER = (datetime.now() + timedelta(days=7))
    ONE_K_DAYS_AGO = (datetime.now() - timedelta(days=1000))

    # 常量
    PERFORMANCE_TARGET = "sharpe"
    ETF_FILE_NAME = "data/ETF.json"
    YFINANCE_FILE_NAME = "combined_stock_data.csv"

    # 監控清單
    WATCH_TARGETS = ["00662.TW", "00770.TW", "00893.TW", "00895.TW", "00916.TW"]
    SPECIAL_TARGETS = ["2330.TW"]



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
    def read_csv(self):
        df = pd.read_csv(ARGS.YFINANCE_FILE_NAME)                
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

class Strategy:
    class Turtle_v4_1(bt.Strategy):
        """
    海龜交易策略（改進版 v4.1）
    ✅ 使用 ADX 過濾盤整市場（ADX > 20）
    ✅ 使用布林通道過濾低波動市場（布林通道寬度 > ATR）
    ✅ **避免當沖**（確保持倉至少一天）
    ✅ **新增日誌記錄**
    ✅ **新增交易範圍控制 (`start_date`, `skip_dates`)**
    ✅ **新增最大倉位限制（最多 90% 資金進場）**
    """

        params = (
            ("entry_period", 20), 
            ("exit_period", 10), 
            ("stock_id", "0050.TW"),  # 股票代號
            ("risk", 0.02),
            ("start_date", datetime(2025, 1, 1)),  # 只在這個日期之後交易
            ("skip_dates", []),  # 這些日期不交易
        )

        def __init__(self):
            stock_id = self.params.stock_id
            entry_period = self.params.entry_period
            exit_period = self.params.exit_period
            log_filename = f"{stock_id}/tutle_strategy_{entry_period}_{exit_period}.log"
            self.logger = init_logger(log_filename)
            # log start and params
            self.logger.debug(f"🔹 回測開始 | 版本: v4.1 | stock_id: {stock_id} | Entry Period: {self.params.entry_period}, Exit Period: {self.params.exit_period}")
            
            
            self.entry_high = bt.indicators.Highest(self.data.high(-1), period=self.params.entry_period)
            self.exit_low = bt.indicators.Lowest(self.data.low(-1), period=self.params.exit_period)
            
            self.adx = bt.indicators.ADX(period=14)
            self.boll = bt.indicators.BollingerBands(period=20)
            self.boll_width = self.boll.lines.top - self.boll.lines.bot
            
            self.atr = bt.indicators.ATR(self.data, period=14)
            
            self.last_trade_date = None
            self.total_commission = 0
            self.signal_list = []

        def next(self):
            trade_date = self.datas[0].datetime.date(0)
            price = self.data.close[0]
            portfolio_value = self.broker.getvalue()

            # 🚀 **過濾：只在 start_date 之後交易**
            if trade_date < self.params.start_date.date():
                return  # 忽略早於 start_date 的訊號
            
            # 🚀 **過濾：跳過指定日期**
            if trade_date in [d.date() for d in self.params.skip_dates]:
                self.logger.debug(f"❌ {trade_date} - 設定為不交易日，跳過")
                return  # 不交易，直接返回

            if self.last_trade_date == trade_date:
                return  # 避免當沖
            
            cash = self.broker.get_cash()
            atr_risk = self.atr[0] * 2
            size = (cash * 1 * self.params.risk) / atr_risk
            
            required_cash = size * price
            max_position_value = cash * 0.9
            if required_cash > max_position_value:
                size = max_position_value / price  # 調整 size 以符合最大倉位限制
            
            size = int(size)
            if  self.adx[0] > 20 and self.boll_width[0] > self.atr[0] and price > self.entry_high[0]:
                self.logger.debug(f"💡 {trade_date} | 嘗試買入 {self.params.stock_id} @ {price:.2f} | Size: {size}")
                self.signal_list.append({ "date": f"{trade_date}",
                            "action": 1,
                            "size": size,
                            "price": price,
                            "total": -size * price,})
                if not self.position or True:
                    self.buy(size=size)
                self.last_trade_date = trade_date
            elif price < self.exit_low[0]:
                self.logger.debug(f"💡 {trade_date} | 嘗試賣出 {self.params.stock_id} @ {price:.2f}")
                if self.position:
                    self.signal_list.append({ "date": f"{trade_date}",
                                "action": -1,
                                "size": -size,
                                "price": price,
                                "total": size * price
                                })
                    self.close()            
                self.last_trade_date = trade_date

        def notify_order(self, order):
            trade_date = self.datas[0].datetime.date(0)
            action = "買進" if order.isbuy() else "賣出"
            cash_remain = self.broker.get_cash()
            portfolio_value = self.broker.getvalue()
            price = order.executed.price if order.executed else 0
            size = order.executed.size if order.executed else 0
            
            if order.status in [order.Completed]:
                cost = order.executed.value
                commission = order.executed.comm
                self.total_commission += commission
                self.logger.debug(f"✅ {trade_date} | {action} @ {price:.2f} | Size: {size}")
                action = "⬅" if size < 0 else "➡" 
                self.logger.debug(f"{action} 交易金額: {cost:.2f} | 現金餘額: {cash_remain:.2f} | 總資產: {portfolio_value:.2f} | 交易成本: {commission:.2f}")

        def stop(self):
            total_commission = self.total_commission
            final_value = self.broker.getvalue()
            self.logger.debug(f"🔹 回測結束 | 版本: v4.1 | stock_id: {self.params.stock_id} | Entry Period: {self.params.entry_period}, Exit Period: {self.params.exit_period}")
            self.logger.debug(f"🔹 最終資產價值: {final_value:.2f} | 總手續費支出: {total_commission:.2f}")

    class Turtle_v4_1_1(bt.Strategy):
        """
        海龜交易策略（改進版 v4.1 + K 線過濾 + 長上影偵測 + 強K加碼）
        ✅ 使用 ADX 過濾盤整市場（ADX > 20）
        ✅ 使用布林通道過濾低波動市場（布林通道寬度 > ATR）
        ✅ 避免當沖（持倉至少一天）
        ✅ 新增 K 線結構過濾假突破：
            - 突破時需為紅K（Close > Open）
            - 收盤需接近最高價（high - close < 實體的一定比例）
        ✅ 新增長上影線出場條件（high - close > 上影線比例）
        ✅ 強K日才允許加碼
        """

        params = (
            ("entry_period", 20), 
            ("exit_period", 10), 
            ("stock_id", "0050.TW"),
            ("risk", 0.02),
            ("start_date", datetime(2025, 1, 1)),
            ("skip_dates", []),
            ("kbar_filter", True),
            ("kbar_strength_ratio", 0.3),
            ("upper_shadow_ratio", 2.0),  # 長上影線條件
        )

        def __init__(self):
            stock_id = self.params.stock_id
            entry_period = self.params.entry_period
            exit_period = self.params.exit_period
            log_filename = f"{stock_id}/tutle_strategy_{entry_period}_{exit_period}.log"
            self.logger = init_logger(log_filename)
            self.logger.debug(f"🔹 回測開始 | 版本: v4.1 + KBar | stock_id: {stock_id} | Entry Period: {self.params.entry_period}, Exit Period: {self.params.exit_period}")

            self.entry_high = bt.indicators.Highest(self.data.high(-1), period=self.params.entry_period)
            self.exit_low = bt.indicators.Lowest(self.data.low(-1), period=self.params.exit_period)

            self.adx = bt.indicators.ADX(period=14)
            self.boll = bt.indicators.BollingerBands(period=20)
            self.boll_width = self.boll.lines.top - self.boll.lines.bot
            self.atr = bt.indicators.ATR(self.data, period=14)

            self.last_trade_date = None
            self.total_commission = 0
            self.signal_list = []

        def next(self):
            trade_date = self.datas[0].datetime.date(0)
            price = self.data.close[0]
            portfolio_value = self.broker.getvalue()

            if trade_date < self.params.start_date.date():
                return
            if trade_date in [d.date() for d in self.params.skip_dates]:
                self.logger.debug(f"❌ {trade_date} - 設定為不交易日，跳過")
                return
            if self.last_trade_date == trade_date:
                return

            cash = self.broker.get_cash()
            atr_risk = self.atr[0] * 2
            size = (cash * self.params.risk) / atr_risk
            required_cash = size * price
            max_position_value = cash * 0.9
            if required_cash > max_position_value:
                size = max_position_value / price
            size = int(size)

            is_breakout = price > self.entry_high[0]
            kbar_body = self.data.close[0] - self.data.open[0]
            upper_shadow = self.data.high[0] - self.data.close[0]
            strong_kbar = self.data.close[0] > self.data.open[0] and \
                        upper_shadow < self.params.kbar_strength_ratio * kbar_body
            long_upper_shadow = upper_shadow > self.params.upper_shadow_ratio * abs(kbar_body)

            if self.adx[0] > 20 and self.boll_width[0] > self.atr[0] and is_breakout:
                if self.params.kbar_filter and not strong_kbar:
                    self.logger.debug(f"⚠️ {trade_date} | 突破但 K 線不夠強（可能是假突破），跳過進場")
                    return

                self.logger.debug(f"💡 {trade_date} | 嘗試買入 {self.params.stock_id} @ {price:.2f} | Size: {size}")
                self.signal_list.append({ "date": f"{trade_date}", "action": 1, "size": size, "price": price, "total": -size * price })
                if not self.position or strong_kbar:  # 只有在強K日才加碼或建倉
                    self.buy(size=size)
                self.last_trade_date = trade_date

            elif price < self.exit_low[0] or long_upper_shadow:
                reason = "突破低點" if price < self.exit_low[0] else "出現長上影線"
                self.logger.debug(f"💡 {trade_date} | 嘗試賣出 {self.params.stock_id} @ {price:.2f} | 原因: {reason}")
                if self.position:
                    self.signal_list.append({ "date": f"{trade_date}", "action": -1, "size": -size, "price": price, "total": size * price })
                    self.close()
                self.last_trade_date = trade_date

        def notify_order(self, order):
            trade_date = self.datas[0].datetime.date(0)
            action = "買進" if order.isbuy() else "賣出"
            cash_remain = self.broker.get_cash()
            portfolio_value = self.broker.getvalue()
            price = order.executed.price if order.executed else 0
            size = order.executed.size if order.executed else 0

            if order.status in [order.Completed]:
                cost = order.executed.value
                commission = order.executed.comm
                self.total_commission += commission
                self.logger.debug(f"✅ {trade_date} | {action} @ {price:.2f} | Size: {size}")
                action = "⬅" if size < 0 else "➡"
                self.logger.debug(f"{action} 交易金額: {cost:.2f} | 現金餘額: {cash_remain:.2f} | 總資產: {portfolio_value:.2f} | 交易成本: {commission:.2f}")

        def stop(self):
            final_value = self.broker.getvalue()
            self.logger.debug(f"🔹 回測結束 | 版本: v4.1 + KBar | stock_id: {self.params.stock_id} | Entry Period: {self.params.entry_period}, Exit Period: {self.params.exit_period}")
            self.logger.debug(f"🔹 最終資產價值: {final_value:.2f} | 總手續費支出: {self.total_commission:.2f}")



class TaiwanStockCommission(bt.CommInfoBase):
    """
    台股交易成本：
    - 買入：收 0.1% 手續費
    - 賣出：收 0.1% 手續費 + 0.3% 交易稅
    """
    params = (
        ("commission", 0.001),  # 手續費 0.1%
        ("stocklike", True),  # 股票類資產
    )

    def _getcommission(self, size, price, pseudoexec):
        cost = abs(size) * price  # 交易金額
        commission = cost * self.p.commission  # 計算手續費
        if size < 0:  # 只有賣出時收交易稅
            commission += cost * 0.003  # 0.3% 交易稅
        return commission


class HoldingPeriodAnalyzer(bt.Analyzer):
    """
    以持倉區段為單位計算持有時間（天數）
    只要持倉中就會計時，無論加碼或減碼
    出場時記錄持有期間（以日期計算天數）
    """
    def __init__(self):
        self.holding_days = []
        self.holding_bars = []
        self.in_position = False
        self.entry_bar = None
        self.entry_date = None

    def next(self):
        pos = self.strategy.getposition()
        has_position = pos.size != 0

        if has_position and not self.in_position:
            # 開始持倉
            self.in_position = True
            self.entry_bar = len(self.strategy)
            self.entry_date = bt.num2date(self.strategy.datas[0].datetime[0]).date()

        elif not has_position and self.in_position:
            # 結束持倉，記錄期間
            exit_bar = len(self.strategy)
            exit_date = bt.num2date(self.strategy.datas[0].datetime[0]).date()

            bar_diff = exit_bar - self.entry_bar
            day_diff = (exit_date - self.entry_date).days

            self.holding_bars.append(bar_diff)
            self.holding_days.append(day_diff)

            self.in_position = False
            self.entry_bar = None
            self.entry_date = None

    def get_analysis(self):
        count = len(self.holding_days)
        if count == 0:
            return {
                'average_bars': 0,
                'average_days': 0,
                'count': 0,
                'holding_bars': [],
                'holding_days': []
            }

        return {
            'average_bars': sum(self.holding_bars) / count,
            'average_days': sum(self.holding_days) / count,
            'count': count,
            'holding_bars': self.holding_bars,
            'holding_days': self.holding_days
        }



# 參數優化
def run_optimization_once(df:pd.DataFrame, ticker:str, strategy:bt.Strategy, print_strat:bool=False, num_transactions:int=5, performance_target:str=ARGS.PERFORMANCE_TARGET):
    cerebro = bt.Cerebro(optreturn=False)
    # trace list: 0050, 2330, 0052, 元大全球 AI（00762）, 00737(國泰全球 AI), 00757(統一 FANG+ ETF)* 00635U.TW(期元大S&P黃金)*
    # 下載並載入數據
    start = ARGS.ONE_K_DAYS_AGO.strftime('%Y-%m-%d')
    end = "2025-03-27"
    # end = one_week_later.strftime('%Y-%m-%d')
    print(f"start: {start}, end: {end}")

    data_1 = Dataloader.from_csv_df(df=df, symbol=ticker, start=ARGS.ONE_K_DAYS_AGO.strftime('%Y-%m-%d'), end=end)
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
        start_date=ARGS.ONE_K_DAYS_AGO,
        entry_period=range(10, 50, 10),  # 測試 10, 20, 30, 40, 50 天突破
        exit_period=range(10, 41, 5)      # 測試 5, 10, 15, 20 天回撤
    )

       # 加入績效分析器
    cerebro.addanalyzer(bt.analyzers.SharpeRatio, _name='sharpe')
    cerebro.addanalyzer(bt.analyzers.DrawDown, _name='drawdown')
    cerebro.addanalyzer(bt.analyzers.TradeAnalyzer, _name='trade')
    cerebro.addanalyzer(bt.analyzers.Transactions, _name='transactions')
    cerebro.addanalyzer(HoldingPeriodAnalyzer, _name='holdings')
    cerebro.addanalyzer(bt.analyzers.TimeReturn, _name='timereturn')
    # cerebro.addstrategy(TurtleStrategy_v1_1_1)
    optimized_results = cerebro.run(maxcpus=1, optreturn=False)
    # print('Ending Portfolio Value: %.2f' % cerebro.broker.getvalue())
    # 遍歷所有優化組合並顯示績效
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

        entry_period = strat.params.entry_period
        exit_period = strat.params.exit_period
        logger = init_logger(f"{ticker}/tutle_strategy_{entry_period}_{exit_period}.log", mode='a')            
            
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
    logger.log(level,f"==========================")
    logger.log(level,f"Stock ID: {stock_id}")
    logger.log(level,f"Entry Period: {bt_result['params'].entry_period}")
    logger.log(level,f"Exit Period: {bt_result['params'].exit_period}")
    logger.log(level,f"Sharpe Ratio: {sharpe:.3f}")
    logger.log(level,f"Max Drawdown: {bt_result['max_drawdown']:.2f}%")
    logger.log(level,f"Win Rate: {bt_result['win_rate']:.2%}")
    logger.log(level,f"Profit Factor: {bt_result['profit_factor']:.2f}")
    logger.log(level,f"Cumulative Return: {bt_result['cumulative_return']:.2%}")
    logger.log(level,f"Annual Return: {annual_return:.2%}")

def init_logger(filename, mode='w'):
    logger = logging.getLogger(filename)
    logger.setLevel(logging.DEBUG)

    # ✅ 確保只添加 handler 一次，避免重複輸出 log
    if not logger.hasHandlers():
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')        
        # ✅ 設定 console handler
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

        # ✅ 設定 file handler（確保 log 不會被重複寫入）
        log_file = Path(f'log/{filename}')
        log_file.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(f'log/{filename}', mode=mode, encoding="utf-8")
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    return logger

def lookup_target():
    dataframe =  Dataloader.read_csv()

    # tutle 4.1 trace list: 0050.TW, 2330.TW, 00757, 00635U.TW, 00893.TW, 00895.TW
    ticker_list_1 = ['00893.TW'] # 第一關注目標
    ticker_list_2 = ['0050.TW', '2330.TW', '00737.TW', '00635U.TW'] # 第二關注目標
    tickers = Dataloader.list_tickers(dataframe)
    logger = init_logger("backtrader.log")
    target_list = tickers  

    # read json from ./data/ETF.json with utf-8           
    # print(f"目標清單: {target_list}")
    num_transactions = 5
    errors = []
    watch_list = []
    
    for ticker in target_list:
        print(f"開始優化 {ticker} 的策略參數")
        best_result = None
        try:
            best_result = run_optimization_once(dataframe, ticker, Strategy.Turtle_v4_1, False, num_transactions, "annual_return")
        except Exception as e:
            print(f"⚠️ 優化 {ticker} 時發生錯誤: {e}")
            logger.error(f"⚠️ 優化 {ticker} 時發生錯誤: {e}")
            errors.append({"ticker": ticker, "error": str(e)})
            continue
        if best_result is not None and best_result['sharpe'] != -float('inf'):
            annual_return = best_result["strat"].analyzers.returns.get_analysis().get("rnorm", None)
            sharpe = best_result["sharpe"]
            if (sharpe < 0 ):
                continue

            print_backtest_result(level=logging.DEBUG, bt_result=best_result, num_transactions=5, filename=f"{ticker}/tutle_strategy.log")

            if sharpe < 0.1:
                continue

            df_trades = []
        # print last x trades
            strat = best_result["strat"]                 
                    
            df_trades = pd.DataFrame(strat.signal_list)
            max_trade_date = df_trades['date'].max()
            #check if max_trade_date is greater than 2025-03-22
            if ( df_trades['action'].iloc[-1]==1 and max_trade_date > ARGS.FIVE_DAYS_AGO_STR):
                watch_list.append({"ticker": ticker, "bt_result": best_result})

        print(f"結束優化 {ticker} 的策略參數")

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

    target_list = ARGS.WATCH_TARGETS  

    num_transactions = 5
    errors = []
    result_list = []
    for ticker in target_list:
        print(f"開始優化 {ticker} 的策略參數")
        best_result = None
        try:
            best_result = run_optimization_once(dataframe, ticker, Strategy.Turtle_v4_1, False, num_transactions, "annual_return")
        except Exception as e:
            print(f"⚠️ 優化 {ticker} 時發生錯誤: {e}")
            logger.error(f"⚠️ 優化 {ticker} 時發生錯誤: {e}")
            errors.append({"ticker": ticker, "error": str(e)})
            continue
        if best_result is not None and best_result['sharpe'] != -float('inf'):
            sharpe = best_result["sharpe"]
            if (sharpe < 0 ):
                continue

            print_backtest_result(level=logging.DEBUG, bt_result=best_result, num_transactions=5, filename=f"{ticker}/tutle_strategy.log")

            if sharpe < 0.1:
                continue

            df_trades = []
        # print last x trades
            strat = best_result["strat"]                 
                    
            df_trades = pd.DataFrame(strat.signal_list)
            max_trade_date = df_trades['date'].max()
            #check if max_trade_date is greater than 2025-03-22
            if ( df_trades['action'].iloc[-1] == -1 ):
                #and max_trade_date > five_days_ago_str
                result_list.append({"ticker": ticker, "bt_result": best_result})

        print(f"結束優化 {ticker} 的策略參數")

    print("🎉 優化完成！")
    for x in result_list:
        print_backtest_result(level=logging.INFO, bt_result=x["bt_result"], num_transactions=5)

def download_data():
    etf_codes = []

    with open(ARGS.ETF_FILE_NAME, 'r', encoding='utf-8') as f:
        data = json.load(f)
        for etf in data:
            code = etf["基金代號"]
            # concat code with .TW
            etf_codes.append(f"{code}.TW")
    
    for ticker in ARGS.SPECIAL_TARGETS:
        etf_codes.append(ticker)

    # 批次下載（預設為每日資料）
    data = yf.download(
        tickers=etf_codes,
        start="1998-01-01",
        end=ARGS.ONE_WEEK_LATER.strftime('%Y-%m-%d'),
        group_by='ticker',   # 會以股票代碼作為 key 分群
        auto_adjust=True,     # 自動調整股價（考慮除權息等）
        progress=True
    )

    # 建立一個空的 DataFrame 用來合併資料
    combined_df = pd.DataFrame()

    # 將每支股票的資料轉成長格式，並加入 Ticker 欄位
    for ticker in etf_codes:
        df = data[ticker].copy()
        df['Ticker'] = ticker
        df = df.reset_index()  # 把日期從 index 轉為欄位
        combined_df = pd.concat([combined_df, df], ignore_index=True)

    # 儲存為單一 CSV
    combined_df.to_csv(ARGS.YFINANCE_FILE_NAME, index=False)

    print(f"✅ 資料已儲存為 {ARGS.YFINANCE_FILE_NAME}")