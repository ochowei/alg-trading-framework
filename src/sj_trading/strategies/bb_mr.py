import backtrader as bt
from datetime import datetime
from sj_trading.logger import init_logger, close_logger
from sj_trading.models import StrategySignal


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
        ("bb_period", 20),
        ("bb_devfactor", 2.0),
        ("atr_period", 14),
        ("risk", 0.1),
        ("max_position_ratio", 0.99),
        ("stock_id", "STOCK.TW"),
        ("start_date", datetime(2025, 6, 1)),
        ("end_date", None),
        ("skip_dates", []),
        ("stop_loss_atr_multiplier", 0),
        ("stop_loss_pct", 0),
    )

    def __init__(self):
        stock_id = self.params.stock_id
        bb_period = self.params.bb_period
        bb_devfactor = self.params.bb_devfactor
        log_filename = f"{stock_id}/bb_mean_reversion_{bb_period}_{bb_devfactor}.log"
        self.logger = init_logger(log_filename, mode='w') # 使用 'w' 覆寫模式開始新回測紀錄
        self.logger.debug(f"🔹 回測開始 | 版本: BB Mean Reversion v1.0 | stock_id: {stock_id} | BB Period: {bb_period}, DevFactor: {bb_devfactor}, Risk: {self.params.risk}")
        if self.params.end_date:
            self.logger.debug(f"🔹 交易區間: {self.params.start_date.date()} 至 {self.params.end_date.date()}")
        else:
            self.logger.debug(f"🔹 交易區間: {self.params.start_date.date()} 至 無限制")

        # 指標定義
        self.bollinger = bt.indicators.BollingerBands(
            self.data.close,
            period=self.params.bb_period,
            devfactor=self.params.bb_devfactor
        )
        self.atr = bt.indicators.ATR(self.data, period=self.params.atr_period)

        # 策略狀態變數
        self.order = None # 用於追蹤待處理訂單
        self.stop_loss_order = None # 用於追蹤停損單
        self.last_trade_date = None # 避免當沖
        self.total_commission = 0 # 累計交易成本
        self.signal_list = []
        # 方便訪問布林通道線路
        self.sma = self.bollinger.lines.mid
        self.top_band = self.bollinger.lines.top
        self.bot_band = self.bollinger.lines.bot

        self.stop_price = None

    def next(self):
        trade_date = self.datas[0].datetime.date(0)
        price = self.data.close[0]
        high = self.data.high[0]
        cash = self.broker.get_cash()
        portfolio_value = self.broker.getvalue()

        # --- 過濾條件 ---
        # 1. 只在 start_date 之後交易
        if trade_date < self.params.start_date.date():
            return

        # 1.b (新增) 只在 end_date 之前交易
        if self.params.end_date and trade_date > self.params.end_date.date():
            return

        # 2. 跳過指定日期
        if trade_date in self.params.skip_dates:
            self.logger.debug(f"❌ {trade_date} - 設定為不交易日，跳過")
            return

        # # 3. 避免當沖 (同一天內不再進行新的開倉或平倉決策)
        # if self.last_trade_date == trade_date:
        #     return

        # # 4. 如果已有掛單，則不進行新操作
        # if self.order:
        #     return

        # --- 策略邏輯 ---
        # 計算倉位大小
        atr_value = self.atr[0]
        if atr_value == 0: # 避免除以零
             self.logger.warning(f"⚠️ {trade_date} | ATR 為 0，無法計算倉位大小")
             return

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
        
        if self.position and self.stop_price and price < self.stop_price:
            self.logger.debug(f"💡 {trade_date} | 價格 {price:.2f} 觸及停損價 {self.stop_price:.2f} | 停損賣出")
            
            # 使用 StrategySignal class
            signal = StrategySignal(
                date=f"{trade_date}",
                ticker=self.params.stock_id,
                action=-1, # 停損賣出 (平倉)
                size=size,
                price=price,
                total=size * price,
                stop_loss_trigger=self.stop_price # 記錄觸發的停損價
            )
            self.signal_list.append(signal.to_dict())
            
            self.close()
            self.last_trade_date = trade_date
            return



        # 進場邏輯：價格跌破下軌且目前無倉位
        if  price < self.bot_band[0]:
            self.logger.debug(f"💡 {trade_date} | 價格 {price:.2f} 跌破下軌 {self.bot_band[0]:.2f} | 嘗試買入 | Size: {size}")
            stop_price = price * (1.0 - self.params.stop_loss_pct)

            if not self.position:
                # 使用 StrategySignal class
                signal = StrategySignal(
                    date=f"{trade_date}",
                    ticker=self.params.stock_id,
                    action=1, # 買入訊號
                    size=size,
                    price=price,
                    total=-size * price,
                    trigger=self.bot_band[0], # 記錄觸發的 BB 下軌價
                    stop_loss=stop_price # 記錄計算出的停損價
                )
                self.signal_list.append(signal.to_dict())
                
                self.order = self.buy(size=size,exectype=bt.Order.Limit, price=(price+high)/2) # 限價單買入              
                self.last_trade_date = trade_date # 記錄交易日期
            else:
                # 使用 StrategySignal class
                signal = StrategySignal(
                    date=f"{trade_date}",
                    ticker=self.params.stock_id,
                    action=3, # 買入訊號 (已持倉)
                    size=size,
                    price=price,
                    total=-size * price,
                    trigger=self.bot_band[0],
                    stop_loss=stop_price
                )
                self.signal_list.append(signal.to_dict())


        # 出場邏輯：價格回升觸及中線且目前持有倉位
        elif price >= self.sma[0] :
            self.logger.debug(f"💡 {trade_date} | 價格 {price:.2f} 回到中線 {self.sma[0]:.2f} | 嘗試賣出 (平倉)")
            
            if self.position:
                # 使用 StrategySignal class
                signal = StrategySignal(
                    date=f"{trade_date}",
                    ticker=self.params.stock_id,
                    action=-1, # 賣出訊號 (平倉)
                    size=size,
                    price=price,
                    total=size * price,
                    trigger=self.sma[0] # 記錄觸發的 SMA 價格
                )
                self.signal_list.append(signal.to_dict())

                if self.stop_loss_order:
                    self.cancel(self.stop_loss_order)
                self.close()
                self.last_trade_date = trade_date # 記錄交易日期
            else:
                # 使用 StrategySignal class
                signal = StrategySignal(
                    date=f"{trade_date}",
                    ticker=self.params.stock_id,
                    action=-3, # 賣出訊號 (未持倉)
                    size=size,
                    price=price,
                    total=size * price,
                    trigger=self.sma[0]
                )
                self.signal_list.append(signal.to_dict())

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
            log_action = "⬅️" if order.issell() else "➡️" # 視覺化買賣方向
            self.logger.debug(f"   {log_action} 交易金額: {cost:.2f} | PnL: {pnl:.2f} | 交易成本: {commission:.2f}")
            self.logger.debug(f"   💰 現金餘額: {cash_remain:.2f} | 總資產: {portfolio_value:.2f}")
            self.order = None

            if order.isbuy():
                # 使用 StrategySignal class
                signal = StrategySignal(
                    date=f"{trade_date}",
                    ticker=self.params.stock_id,
                    action=2, # 買入成交
                    size=size,
                    price=price,
                    total=-size * price, # 買入成本為負
                    pnl=pnl # 記錄 PnL
                )
                self.signal_list.append(signal.to_dict())

                stop_price = 0
                log_msg = ""

                # ... (停損單邏輯) ...

            elif order.issell():
                # 使用 StrategySignal class
                signal = StrategySignal(
                    date=f"{trade_date}",
                    ticker=self.params.stock_id,
                    action=-2, # 賣出成交
                    size=size,
                    price=price,
                    total=size * price, # 賣出收入為正 (原碼為 -size*price, 這裡修正為正)
                    pnl=pnl # 記錄 PnL
                )
                self.signal_list.append(signal.to_dict())
                self.stop_loss_order = None

        elif order.status in [order.Canceled, order.Margin, order.Rejected]:
            # self.logger.warning(f"⚠️ {trade_date} | 訂單未能完成 | Status: {status}")
            if self.stop_loss_order and self.stop_loss_order.ref == order.ref:
                self.stop_loss_order = None
            self.order = None

    def stop(self):
        final_value = self.broker.getvalue()
        self.logger.debug("="*20 + " 回測結束 " + "="*20)
        self.logger.debug(f"🔹 最終資產價值: {final_value:.2f}")
        self.logger.debug(f"🔹 總手續費支出: {self.total_commission:.2f}")
        self.logger.debug(f"🔹 使用參數: BB Period={self.params.bb_period}, DevFactor={self.params.bb_devfactor}, Risk={self.params.risk}")
        self.logger.debug("="*50)
        close_logger(self.logger)