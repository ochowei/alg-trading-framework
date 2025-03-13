import backtrader as bt

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