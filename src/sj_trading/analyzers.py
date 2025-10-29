import backtrader as bt

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
