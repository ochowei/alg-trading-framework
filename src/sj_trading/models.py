# src/sj_trading/models.py

from dataclasses import dataclass, asdict
from typing import Optional

@dataclass
class StrategySignal:
    """
    統一儲存策略訊號的資料類別。
    這是策略 (strategies) 和 模擬器 (simulation) 之間的
    標準資料交換格式 (Data Transfer Object)。
    """
    
    # --- 核心欄位 ---
    date: str
    action: int 
    size: int
    price: float
    total: float

    # --- 可選欄位 ---
    trigger: Optional[float] = None
    stop_loss: Optional[float] = None
    stop_loss_trigger: Optional[float] = None
    pnl: Optional[float] = None

    def to_dict(self):
        return asdict(self)