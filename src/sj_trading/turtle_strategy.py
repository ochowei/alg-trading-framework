import backtrader as bt
import shioaji as sj
from datetime import datetime
import logging
from .logger import init_logger

class TurtleStrategy_v1_1(bt.Strategy):
    """
    海龜交易策略（Turtle Trading Strategy）v1.1
    - 進場條件：價格突破過去 20 天最高價
    - 出場條件：價格跌破過去 10 天最低價
    - 倉位管理：使用 ATR（平均真實範圍）計算動態倉位大小
    - 風險管理：每筆交易風險設定為 2%（可調整）

    版本號: v1.1
    主要改進：
    ✅ entry_period=20, exit_period=10（經典參數）
    ✅ 加入 ATR 動態倉位管理，避免市場波動影響交易大小
    ✅ 每次交易最大風險限制為 2%
    ✅ 自動輸出回測績效數據
    """

    params = (("entry_period", 20),  # 進場週期（突破 20 天新高）
              ("exit_period", 10),   # 出場週期（跌破 10 天低點）
              ("risk", 0.02))         # 單筆交易最大風險 2%

    def __init__(self):
        self.entry_high = bt.indicators.Highest(self.data.high(-1), period=self.params.entry_period)
        self.exit_low = bt.indicators.Lowest(self.data.low(-1), period=self.params.exit_period)
        self.atr = bt.indicators.ATR(self.data, period=14)
        self.last_trade_date = None  # 記錄最後交易的日期
        self.position_entry_date = None  # 記錄最後進場日期，防止當天賣出

    def next(self):
        current_atr = self.atr[0]  # 取得當前 ATR
        trade_date = self.datas[0].datetime.date(0)
        # ✅ 避免當天內賣出，確保持倉至少 1 天
        if self.position and self.position_entry_date == trade_date:
            return

        # ✅ 確保每天最多只交易一次
        if self.last_trade_date == trade_date:
            return

        cash = self.broker.get_cash()
        atr_risk = self.atr[0] * 2
        size = (cash * self.params.risk) / atr_risk
        # print(f"{close:.2f}, {entry_high:.2f}")

        # if trade_date < datetime(2025, 1, 1).date():
        #     return

        if not self.position and self.data.close[0] > self.entry_high[0]:
            self.buy(size=size)
            self.last_trade_date = trade_date
            self.position_entry_date = trade_date  # 記錄買入的日期
        elif self.position and self.data.close[0] < self.exit_low[0]:
            self.close()
            self.last_trade_date = trade_date

    def stop(self):
        total_commission = self.broker.get_value() - self.broker.cash
        final_value = self.broker.getvalue()
        print(f"🔹 回測結束 | 版本: v1.1 | Entry Period: {self.params.entry_period}, Exit Period: {self.params.exit_period}")
        print(f"最終資產價值: {final_value:.2f} | 總手續費支出: {total_commission:.2f} |")

    # def notify_order(self, order):
    #   if order.status in [order.Completed]:  # 確保交易完成後記錄
    #       trade_date = self.datas[0].datetime.date(0)
    #       action = "B買" if order.isbuy() else "S賣"
    #       cost = order.executed.value  # 交易金額
    #       commission = order.executed.comm  # 交易手續費 + 交易稅
    #       portfolio_value = self.broker.getvalue()  # 當前資產總額
    #       cash_remain = self.broker.get_cash()
    #       print(f"{trade_date} | {action} | 交易金額: {cost:.2f} | cash_remain: {cash_remain:.2f} | 成本: {commission:.2f} | 資產總額: {portfolio_value:.2f}")
    def notify_order(self, order):
        if order.status in [order.Completed]:  # 確保交易完成後記錄
            trade_date = self.datas[0].datetime.date(0)
            action = "買進" if order.isbuy() else "賣出"
            price = order.executed.price  # 成交價格
            cost = order.executed.value  # 交易金額
            commission = order.executed.comm  # 交易手續費
            cash_remain = self.broker.get_cash()
            portfolio_value = self.broker.getvalue()

            print(f"📌 訊號日期: {trade_date} | {action} @ {price:.2f}")
            print(f"➡ 交易金額: {cost:.2f} | 現金餘額: {cash_remain:.2f} | 總資產: {portfolio_value:.2f} | 交易成本: {commission:.2f}")


import backtrader as bt

class TurtleStrategy_v4_0(bt.Strategy):
    """
    海龜交易策略（改進版 v4.0）
    ✅ 使用 ADX 過濾盤整市場（ADX > 20）
    ✅ 使用布林通道過濾低波動市場（布林通道寬度 > ATR）
    ✅ **避免當沖**（確保持倉至少一天）
    """

    params = (("entry_period", 20), ("exit_period", 10), ("risk", 0.02))

    def __init__(self):
        self.entry_high = bt.indicators.Highest(self.data.high(-1), period=self.params.entry_period)
        self.exit_low = bt.indicators.Lowest(self.data.low(-1), period=self.params.exit_period)

        # ADX 趨勢判斷
        self.adx = bt.indicators.ADX(period=14)

        # 布林通道
        self.boll = bt.indicators.BollingerBands(period=20)
        self.boll_width = self.boll.lines.top - self.boll.lines.bot  # 計算通道寬度

        # ATR 參考
        self.atr = bt.indicators.ATR(self.data, period=14)

        # 記錄最後交易日期（避免當沖）
        self.last_trade_date = None

    def notify_order(self, order):
        if order.status in [order.Completed]:
            trade_date = self.datas[0].datetime.date(0)
            action = "B買" if order.isbuy() else "S賣"
            cost = order.executed.value
            commission = order.executed.comm  # 交易手續費 + 交易稅
            portfolio_value = self.broker.getvalue()  # 當前資產總額
            cash_remain = self.broker.get_cash()
            print(f"{trade_date} | {action} | 交易金額: {cost:.2f} | cash_remain: {cash_remain:.2f} | 成本: {commission:.2f} | 資產總額: {portfolio_value:.2f}")

            # 記錄最後交易日期
            self.last_trade_date = trade_date

    def next(self):
        cash = self.broker.get_cash()
        atr_risk = self.atr[0] * 2  # ATR 風險控制
        size = (cash * self.params.risk) / atr_risk  # 計算交易股數
        today = self.datas[0].datetime.date(0)  # 取得今天日期

        # **避免當沖機制**
        if self.last_trade_date == today:
            return  # 如果今天已經交易過，則不再進行任何交易

        if not self.position:
            if (self.adx[0] > 20 and self.boll_width[0] > self.atr[0] and self.data.close[0] > self.entry_high[0]):
                self.buy(size=size)
        else:
            if self.data.close[0] < self.exit_low[0]:
                self.close()

    def stop(self):
        total_commission = self.broker.get_value() - self.broker.cash
        final_value = self.broker.getvalue()
        print(f"🔹 回測結束 | 版本: v1.1 | Entry Period: {self.params.entry_period}, Exit Period: {self.params.exit_period}")
        print(f"最終資產價值: {final_value:.2f} | 總手續費支出: {total_commission:.2f} |")

class TurtleStrategy_v1_1_1(bt.Strategy):
    """
    海龜交易策略 v1.1.1（基於 v1.1）
    - 新增功能：
      ✅ 只在 `start_date` 之後交易
      ✅ `skip_dates` 中的日期不交易
    """

    params = (("entry_period", 20),
              ("exit_period", 10),
              ("stock_id", "2330.TW"),
              ("risk", 0.02),
              ("start_date", datetime(2025, 1, 1)),  # 只在這個日期之後交易
              ("skip_dates", []),  # 這些日期不交易
             )

    def __init__(self):
        self.entry_high = bt.indicators.Highest(self.data.high(-1), period=self.params.entry_period)
        self.exit_low = bt.indicators.Lowest(self.data.low(-1), period=self.params.exit_period)
        self.atr = bt.indicators.ATR(self.data, period=14)
        self.last_trade_date = None
        self.position_entry_date = None
        self.logger = init_logger()
        self.logger.info(f"🔹 回測開始 | 版本: v1.1.1 | Entry Period: {self.params.entry_period}, Exit Period: {self.params.exit_period}")


    def next(self):
        trade_date = self.datas[0].datetime.date(0)
        price = self.data.close[0]
        portfolio_value = self.broker.getvalue()

        # 🚀 **過濾：只在 start_date 之後交易**
        if trade_date < self.params.start_date.date():
            return  # 忽略早於 start_date 的訊號
        
        # ✅ 避免當天內賣出，確保持倉至少 1 天
        if self.position and self.position_entry_date == trade_date:
            return

        # ✅ 確保每天最多只交易一次
        if self.last_trade_date == trade_date:
            return

        cash = self.broker.get_cash()
        atr_risk = self.atr[0] * 2
        size = (cash * self.params.risk) / atr_risk
        price = self.data.close[0]

        # 🚀 計算下單所需資金
        required_cash = size * price

        # ✅ **設定最大倉位比例**
        max_position_value = cash * 0.9  # 只允許最多 90% 資金進場
        if required_cash > max_position_value:
            size = max_position_value / price  # 調整 size 以符合最大倉位限制

        # ✅ **確保最終 size 是整數**
        size = int(size)

        # ✅ 進場條件：突破 20 天新高
        if not self.position and self.data.close[0] > self.entry_high[0]:
            # 🚀 **過濾：跳過指定日期**
            if trade_date in [d.date() for d in self.params.skip_dates]:
                self.logger.info(f"❌ {trade_date} - 設定為不交易日，跳過")
                return  # 不交易，直接返回
                
            self.logger.info(f"💡 訊號日期: {trade_date} | 嘗試買入 @ {price:.2f} | Size: {size}")
            self.buy(size=size)
            self.last_trade_date = trade_date
            self.position_entry_date = trade_date  # 記錄買入的日期
        elif self.position and self.data.close[0] < self.exit_low[0]:           
            if trade_date in [d.date() for d in self.params.skip_dates]:
                self.logger.info(f"❌ {trade_date} - 設定為不交易日，跳過")
                return  # 不交易，直接返回
            
            self.logger.info(f"💡 訊號日期: {trade_date} | 嘗試賣出 @ {price:.2f}")
            self.close()
            self.last_trade_date = trade_date

    def stop(self):
        total_commission = self.broker.get_value() - self.broker.cash
        final_value = self.broker.getvalue()
        self.logger.info(f"🔹 回測結束 | 版本: v1.1.1 | stock_id: {self.params.stock_id} | Entry Period: {self.params.entry_period}, Exit Period: {self.params.exit_period}")
        self.logger.info(f"🔹 最終資產價值: {final_value:.2f} | 總手續費支出: {total_commission:.2f} |")

    def notify_order(self, order):
        trade_date = self.datas[0].datetime.date(0)
        action = "買進" if order.isbuy() else "賣出"
        cash_remain = self.broker.get_cash()
        portfolio_value = self.broker.getvalue()
        price = order.created.price if order.created.price else 0
        size = order.created.size if order.created.size else 0
        required_margin = price * size

        if order.status in [order.Submitted]:
            self.logger.info(f"📌 {trade_date} | 訂單已提交: {action} @ {price:.2f} | 倉位大小: {size}")

        elif order.status in [order.Accepted]:
            self.logger.info(f"📌 {trade_date} | 訂單已接受: {action} @ {price:.2f} | 倉位大小: {size}")

        elif order.status in [order.Completed]:  
            executed_price = order.executed.price
            cost = order.executed.value
            commission = order.executed.comm

            self.logger.info(f"✅ 交易完成 | {trade_date} | {action} @ {executed_price:.2f} | 倉位大小: {size}")
            self.logger.info(f"     ➡ 交易金額: {cost:.2f} | 現金餘額: {cash_remain:.2f} | 總資產: {portfolio_value:.2f} | 交易成本: {commission:.2f}")

        elif order.status in [order.Canceled]:
            self.logger.warning(f"❌ {trade_date} | 訂單已取消: {action} @ {price:.2f} | 倉位大小: {size}")

        elif order.status in [order.Margin]:  
            self.logger.error(f"⚠️ {trade_date} | 保證金不足，無法執行: {action} @ {price:.2f} | 倉位大小: {size}")
            self.logger.error(f"     ➡ 需要保證金: {required_margin:.2f} | 當前現金: {cash_remain:.2f} | 總資產: {portfolio_value:.2f}")

        elif order.status in [order.Rejected]:
            self.logger.error(f"❌ {trade_date} | 訂單被拒絕: {action} @ {price:.2f} | 倉位大小: {size}")





class TurtleStrategy_v4_1(bt.Strategy):
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
