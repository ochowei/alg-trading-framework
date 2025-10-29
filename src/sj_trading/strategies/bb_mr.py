import backtrader as bt
from datetime import datetime
from src.sj_trading.logger import init_logger

class BollingerBandsMeanReversion(bt.Strategy):
    """
    布林通道均值回歸策略 (Bollinger Bands Mean Reversion Strategy)
    - 進場條件：價格跌破布林通道下軌
    - 出場條件：價格回升觸及布林通道中線 (SMA)
    - 風險管理：使用 ATR 計算動態倉位大小，限制單筆風險
    - 沿用框架：日誌記錄, 交易範圍控制, 避免當沖, 最大倉位限制

    版本號: v1.0
    """

    params = (
        ("bb_period", 20),         # 布林通道週期
        ("bb_devfactor", 2.0),     # 布林通道標準差倍數
        ("atr_period", 14),        # ATR 週期，用於計算倉位
        ("risk", 0.1),            # 單筆交易最大風險比例 (例如 0.02 代表 2%)
        ("max_position_ratio", 0.99), # 最大倉位佔總資金比例 (例如 0.9 代表 90%)
        ("stock_id", "STOCK.TW"),  # 股票代號 (用於日誌檔名)
        ("start_date", datetime(2025, 1, 1)), # 只在此日期之後交易
        ("skip_dates", []),        # 這些日期不交易 (datetime.date 物件列表)
    )

    def __init__(self):
        stock_id = self.params.stock_id
        bb_period = self.params.bb_period
        bb_devfactor = self.params.bb_devfactor
        log_filename = f"{stock_id}/bb_mean_reversion_{bb_period}_{bb_devfactor}.log"
        self.logger = init_logger(log_filename, mode='w') # 使用 'w' 覆寫模式開始新回測紀錄
        self.logger.debug(f"🔹 回測開始 | 版本: BB Mean Reversion v1.0 | stock_id: {stock_id} | BB Period: {bb_period}, DevFactor: {bb_devfactor}, Risk: {self.params.risk}")

        # 指標定義
        self.bollinger = bt.indicators.BollingerBands(
            self.data.close,
            period=self.params.bb_period,
            devfactor=self.params.bb_devfactor
        )
        self.atr = bt.indicators.ATR(self.data, period=self.params.atr_period)

        # 策略狀態變數
        self.order = None # 用於追蹤待處理訂單
        self.last_trade_date = None # 避免當沖
        self.total_commission = 0 # 累計交易成本
        self.signal_list = []
        # 方便訪問布林通道線路
        self.sma = self.bollinger.lines.mid
        self.top_band = self.bollinger.lines.top
        self.bot_band = self.bollinger.lines.bot

    def next(self):
        trade_date = self.datas[0].datetime.date(0)
        price = self.data.close[0]
        cash = self.broker.get_cash()
        portfolio_value = self.broker.getvalue()

        # --- 過濾條件 ---
        # 1. 只在 start_date 之後交易
        if trade_date < self.params.start_date.date():
            return

        # 2. 跳過指定日期
        if trade_date in self.params.skip_dates:
            self.logger.debug(f"❌ {trade_date} - 設定為不交易日，跳過")
            return

        # 3. 避免當沖 (同一天內不再進行新的開倉或平倉決策)
        if self.last_trade_date == trade_date:
            return

        # 4. 如果已有掛單，則不進行新操作
        if self.order:
            return

        # --- 策略邏輯 ---
        # 計算倉位大小
        atr_value = self.atr[0]
        if atr_value == 0: # 避免除以零
             self.logger.warning(f"⚠️ {trade_date} | ATR 為 0，無法計算倉位大小")
             return

        # 風險額度 = 帳戶總值 * 風險比例
        risk_amount = portfolio_value * self.params.risk
        # 每股曝險 = ATR * (某個倍數，例如 2) -> 這裡簡單用 ATR 本身作為波動參考
        # 或者更簡單地，直接用價格的某個百分比，例如 1%
        # risk_per_share = atr_value * 2
        # size = risk_amount / risk_per_share

        # 另一種簡化倉位計算：使用固定比例的資金
        target_value = portfolio_value * self.params.risk # 每次投入風險比例的資金
        size = target_value / price


        # 倉位大小上限控制
        max_position_value = cash * self.params.max_position_ratio
        required_cash = size * price
        if required_cash > max_position_value:
            size = max_position_value / price # 調整 size
            self.logger.debug(f"⚠️ {trade_date} | 觸發最大倉位限制，調整下單 Size 為 {int(size)}")

        size = int(size) # 確保是整數股數
        if size <= 0: # 避免下單 0 股
            return

        # 進場邏輯：價格跌破下軌且目前無倉位
        if not self.position and price < self.bot_band[0]:
            self.logger.debug(f"💡 {trade_date} | 價格 {price:.2f} 跌破下軌 {self.bot_band[0]:.2f} | 嘗試買入 | Size: {size}")
            self.order = self.buy(size=size)
            self.signal_list.append({ "date": f"{trade_date}", "action": 1, "size": size, "price": price, "total": -size * price })

            self.last_trade_date = trade_date # 記錄交易日期

        # 出場邏輯：價格回升觸及中線且目前持有倉位
        elif self.position and price >= self.sma[0]:
            self.logger.debug(f"💡 {trade_date} | 價格 {price:.2f} 回到中線 {self.sma[0]:.2f} | 嘗試賣出 (平倉)")
            self.order = self.close() # 平掉所有倉位
            self.signal_list.append({ "date": f"{trade_date}", "action": -1, "size": size, "price": price, "total": size * price })

            self.last_trade_date = trade_date # 記錄交易日期

    def notify_order(self, order):
        trade_date = self.datas[0].datetime.date(0)
        action = "買進" if order.isbuy() else "賣出"
        status = order.getstatusname()
        price = order.executed.price if order.executed else 0
        size = order.executed.size if order.executed else 0

        self.logger.debug(f"  ➡️ {trade_date} | 訂單通知 | Ref: {order.ref} | Type: {action} | Status: {status} | Size: {size} | Price: {price:.2f}")

        if order.status in [order.Completed]:
            cost = order.executed.value
            commission = order.executed.comm
            self.total_commission += commission
            cash_remain = self.broker.get_cash()
            portfolio_value = self.broker.getvalue()
            pnl = order.executed.pnl
            self.logger.debug(f"✅ {trade_date} | 交易完成 @ {price:.2f} | Size: {size}")
            log_action = "⬅️" if size < 0 else "➡️" # 視覺化買賣方向
            self.logger.debug(f"   {log_action} 交易金額: {cost:.2f} | PnL: {pnl:.2f} | 交易成本: {commission:.2f}")
            self.logger.debug(f"   💰 現金餘額: {cash_remain:.2f} | 總資產: {portfolio_value:.2f}")
            self.order = None # 訂單完成，清除追蹤

        elif order.status in [order.Canceled, order.Margin, order.Rejected]:
            self.logger.warning(f"⚠️ {trade_date} | 訂單未能完成 | Status: {status}")
            self.order = None # 訂單失敗，清除追蹤

    def stop(self):
        final_value = self.broker.getvalue()
        self.logger.debug("="*20 + " 回測結束 " + "="*20)
        self.logger.debug(f"🔹 最終資產價值: {final_value:.2f}")
        self.logger.debug(f"🔹 總手續費支出: {self.total_commission:.2f}")
        self.logger.debug(f"🔹 使用參數: BB Period={self.params.bb_period}, DevFactor={self.params.bb_devfactor}, Risk={self.params.risk}")
        self.logger.debug("="*50)
