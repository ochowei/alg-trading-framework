from datetime import datetime, timedelta

class Config:
    """存放所有預定義的參數和常量"""

    # 日期相關變數
    FIVE_DAYS_AGO_STR = (datetime.now() - timedelta(days=5)).strftime('%Y-%m-%d')
    ONE_WEEK_LATER = (datetime.now() + timedelta(days=7))
    ONE_THOUSAND_DAYS_AGO = (datetime.now() - timedelta(days=1000))

    # 常量
    PERFORMANCE_TARGET = "sharpe"
    YFINANCE_FILE_NAME = "combined_stock_data.csv"

    # 監控清單
    WATCH_TARGETS = []

    OPT_PARAMETERS_TUTLE_4_1 = {
        "start_date": ONE_THOUSAND_DAYS_AGO,
        "entry_period": range(10, 50, 10),
        "exit_period": range(10, 41, 5)
    }

    OPT_PARAMETERS_TUTLE_4_1_1 = {
        "start_date": ONE_THOUSAND_DAYS_AGO,
        "entry_period": range(10, 20, 30),
        "exit_period": range(10, 41, 5),
        "kbar_filter": True,
        "kbar_strength_ratio": [0.2, 0.5, 0.7],
        "upper_shadow_ratio": [1.5, 2.0, 2.5],
    }

    OPT_PARAMETERS_BB_MR = {
        "start_date": datetime(2025, 8, 1),
        "end_date": datetime(2025, 11, 1),
        "bb_period":  range(5,31,5),
        "bb_devfactor":  [1.2,1.4,1.6,1.8, 2.0, 2.2],
        "risk": [0.9],
        "stop_loss_atr_multiplier": [0],
        "stop_loss_pct": [0.05],
    }

    OPT_PARAMETERS_RSI_MR = {
        "start_date": ONE_THOUSAND_DAYS_AGO,
        "rsi_period": [3, 5, 10],
        "rsi_oversold": [5, 20, 25, 30],
        "rsi_exit_level": [30, 60],
        "risk": [ 0.9],
    }
