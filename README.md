# 演算法交易框架

本專案是一個使用 Python 開發的量化交易回測與模擬框架，旨在提供一個模組化、易於擴展的平台，幫助開發者與研究員測試與驗證交易策略。

## 🚀 功能特色 (Features)

本框架的核心功能圍繞著資料處理、策略回測與交易模擬，提供了一個完整的解決方案：

*   **策略支援 (Strategy Support)**
    *   內建多種交易策略範例，位於 `src/sj_trading/strategies/` 目錄。
    *   **布林通道均值回歸 (`bb_mr.py`)**: 基於布林通道指標，當價格觸及通道邊緣時進行反向交易。
    *   **RSI 均值回歸 (`rsi_mr.py`)**: 利用相對強弱指數 (RSI) 的超買與超賣訊號來執行交易。
    *   **海龜交易法 (`turtle.py`)**: 實現經典的海龜交易法則，一個基於通道突破的趨勢追蹤策略。

*   **資料處理 (Data Handling)**
    *   **自動化資料下載**: `download_data.py` 模組支援從 Yahoo Finance (`yfinance`) 下載大量歷史股價資料，並可通過 `data/US_ticker_categories.json` 設定股票池。
    *   **彈性的資料載入器**: `dataloader.py` 提供了一個 `Dataloader` 類別，能將 CSV 格式的本地資料或 `yfinance` 下載的資料轉換為 `backtrader` 框架所需的格式，無縫接軌回測引擎。

*   **回測引擎 (Backtesting Engine)**
    *   **策略執行與訊號產生**: `run_strategy.py` 負責讀取策略設定，執行 `backtrader` 回測，並產生標準化的交易訊號 JSON 檔案 (`strategy_trades.json`)。
    *   **高擬真交易模擬**: `simulation.py` 提供了一個強大的交易模擬器，支援兩種不同的執行模式，處理 T+1 交割、現金管理、整股交易等細節，讓回測結果更貼近真實市場。

*   **結果分析 (Result Analysis)**
    *   **自定義分析器**: `analyzers.py` 中包含了 `HoldingPeriodAnalyzer`，可客製化分析指標，例如計算平均持倉天數等，幫助使用者更深入地評估策略表現。

## 🛠️ 安裝教學 (Installation Guide)

請依照以下步驟來設定您的開發環境。

### 1. 環境準備

*   **Python 版本**: 建議使用 Python 3.12。您可以透過 `.python-version` 檔案確認。
*   **虛擬環境**: 為了保持依賴的隔離，強烈建議建立一個虛擬環境。

### 2. 安裝步驟

1.  **複製專案**
    ```bash
    git clone https://github.com/your-username/sj-trading.git
    cd sj-trading
    ```

2.  **建立虛擬環境 (使用 `uv`)**
    `uv` 是一個極速的 Python 套件管理器。如果您尚未安裝，請參考 [uv 官方文件](https://github.com/astral-sh/uv)。
    ```bash
    uv venv
    ```
    這會在專案根目錄建立一個名為 `.venv` 的虛擬環境。

3.  **啟動虛擬環境**
    *   在 macOS / Linux 上:
        ```bash
        source .venv/bin/activate
        ```
    *   在 Windows 上:
        ```bash
        .venv\Scripts\activate
        ```

4.  **安裝依賴**
    專案使用 `pyproject.toml` 管理依賴。`uv.lock` 檔案確保您安裝的套件版本與開發環境一致。
    ```bash
    uv pip sync
    ```
    或者，如果您想以可編輯模式安裝，以便進行開發：
    ```bash
    uv pip install -e .
    ```

完成以上步驟後，您的開發環境就設定完畢了！您可以使用 `pyproject.toml` 中定義的腳本來執行程式，例如：
```bash
uv run download_data
```
