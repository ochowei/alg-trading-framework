from FinMind import strategies
from FinMind.data import DataLoader
import pandas as pd

data_loader = DataLoader()
# 6877，　8937
bt = strategies.BackTest(
    stock_id="6877",
    start_date="2025-01-18",
    end_date="2025-05-14",
    trader_fund=500000.0,
    fee=0.001425,
    data_loader=data_loader,
)

# 設定策略
bt.add_strategy(strategies.ShortSaleMarginPurchaseRatio)

# 回測
bt.simulate()


# 回測詳細資料
trade_detail = bt.trade_detail

# 大盤累積報酬和回測累積報酬走勢
compare_market_detail = bt.compare_market_detail

# 回測結果，包含總報酬(FinalProfitPer)、年化報酬(AnnualReturnPer)、最大損失(MaxLoss)、最大損失比例(MaxLossPer)...等
final_stats = bt.final_stats

# 大盤年化報酬率和策略年化報酬率
compare_market_stats = bt.compare_market_stats

pd.set_option('display.float_format', '{:.2f}'.format)
pd.set_option("display.max_rows", None)  # 顯示所有列
pd.set_option('display.max_rows', 100)  # 設定最多顯示 100 行
print(trade_detail.tail(100).to_string())