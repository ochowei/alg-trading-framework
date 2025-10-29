import backtrader as bt
from datetime import datetime
from src.sj_trading.logger import init_logger

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
        kbar_strength_ratio = self.params.kbar_strength_ratio
        upper_shadow_ratio = self.params.upper_shadow_ratio

        log_filename = f"{stock_id}/tutle_strategy_{entry_period}_{exit_period}_{kbar_strength_ratio}_{upper_shadow_ratio}.log"
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
