import argparse
import pandas as pd
from decimal import Decimal, ROUND_HALF_UP, ROUND_FLOOR
def simulate_trades(file_path, initial_capital, show_non_executed_orders=False):
    """
    根據用戶指定的規則模擬交易。

    規則：
    1. 初始資金 10,000。
    2. 只處理 action == 2 (買入) 和 action == -2 (賣出)。
    3. 忽略 action == 1 和 action == -1。
    4. 按日期處理。
    5. 同一天內，先處理所有賣出 (-2)，再處理所有買入 (2)。
    6. 買入 (2) 時：
       a. 統計當天所有 '2' 訊號的數量 n。
       b. 將 *目前所有現金* 均分為 n 份。
       c. 根據每份資金和價格，買入對應的股票。
       d. 如果現金不足 (cash == 0)，則無法購買。
    7. 賣出 (-2) 時：
       a. 賣出投資組合中該股票的 *全部* 持股。
       b. 將賣出所得加回現金。
    8. 結束時：
       a. 總結餘 = 最終現金 + 剩餘持股的 *成本價值*。

    （使用 Decimal 來提高財務計算的精度）
    """
    try:
        df = pd.read_json(file_path)
    except Exception as e:
        print(f"讀取 JSON 檔案時出錯: {e}")
        return

    # 確保按日期排序
    df['date'] = pd.to_datetime(df['date'])
    df = df.sort_values(by='date')

    # 使用 Decimal 進行高精度計算
    cash = Decimal(str(initial_capital))
    portfolio = {}  # 格式: {'TICKER': {'size': Decimal, 'cost_basis': Decimal, 'total_cost': Decimal}}

    # 用於格式化輸出的 Decimal
    ZERO = Decimal('0.00')
    CENTS = Decimal('0.01')

    print(f"--- 模擬開始 ---")
    print(f"初始資金: ${cash.quantize(CENTS, rounding=ROUND_HALF_UP):,}")
    print("-" * 30)

    unique_dates = df['date'].unique()

    for date in unique_dates:
        print("-" * 30 + f" {date} " + "-" * 30)

        day_trades = df[df['date'] == date]
        date_str = str(pd.to_datetime(date).date())
        pending_settlement = Decimal('0.0')

        # 1. --- 處理當天的所有賣出 (action == -2) ---
        sells = day_trades[day_trades['action'] == -2]
        for _, row in sells.iterrows():
            ticker = row['ticker']
            sell_price = Decimal(str(row['price']))

            if ticker in portfolio:
                position = portfolio.pop(ticker) # 賣出全部，所以用 pop
                size_held = position['size']
                cash_received = size_held * sell_price
                pending_settlement += cash_received

                print(f"{date_str} [賣出完成] {ticker}:")
                print(f"  > 賣出完成 {size_held:.4f} 股 @ ${sell_price:,.2f}，獲得 ${cash_received.quantize(CENTS, rounding=ROUND_HALF_UP):,}")
                print(f"  > 目前現金: ${cash.quantize(CENTS, rounding=ROUND_HALF_UP):,}")
            # else:
                # print(f"{date_str} [賣出訊號] {ticker}: 投資組合中無此股票，忽略。")


        # 2. --- 處理當天的所有買入 (action == 2) ---
        buys = day_trades[day_trades['action'] == 2]
        num_buys = len(buys)

        if num_buys > 0 and cash > Decimal('0.01'): # 確保有現金且有買入訊號
            cash_per_buy = cash / Decimal(num_buys)

            print(f"{date_str} [買入完成] {num_buys} 個。可用現金 ${cash.quantize(CENTS, rounding=ROUND_HALF_UP):,}，每個訊號分配 ${cash_per_buy.quantize(CENTS, rounding=ROUND_HALF_UP):,}")

            current_cash_for_day = cash # 暫存當天一開始用於分配的現金
            cash = Decimal('0.0') # 先假設所有現金都分配出去

            for _, row in buys.iterrows():
                ticker = row['ticker']
                buy_price = Decimal(str(row['price']))

                if buy_price > 0 and cash_per_buy > 0:
                    # 根據分配的現金，計算可負擔的整數股數 (無條件捨去)
                    size_to_buy = (cash_per_buy / buy_price).to_integral_value(rounding=ROUND_FLOOR)
                    if size_to_buy <= 0:
                        print(f"  > [買入跳過] {ticker}: 分配現金 ${cash_per_buy.quantize(CENTS, rounding=ROUND_HALF_UP):,} 無法購買任何股數 @ ${buy_price:,.2f}。")
                        # 將分配的現金加回主現金池
                        cash += cash_per_buy
                        continue

                    # 根據整數股數計算實際成本
                    actual_cost_of_buy = size_to_buy * buy_price

                    # 計算此筆分配中未花費的餘額
                    unspent_cash = cash_per_buy - actual_cost_of_buy

                    # 將未花費的餘額加回主現金池
                    cash += unspent_cash

                    if ticker in portfolio:
                        # 已持有，加倉並計算平均成本
                        old_size = portfolio[ticker]['size']
                        old_total_cost = portfolio[ticker]['total_cost']

                        new_total_cost = old_total_cost + actual_cost_of_buy
                        new_size = old_size + size_to_buy
                        new_cost_basis = new_total_cost / new_size

                        portfolio[ticker] = {
                            'size': new_size,
                            'cost_basis': new_cost_basis,
                            'total_cost': new_total_cost
                        }
                        print(f"  > [加倉完成] {ticker}: 投入 ${actual_cost_of_buy.quantize(CENTS, rounding=ROUND_HALF_UP):,} 購買 {size_to_buy:.0f} 股 @ ${buy_price:,.2f}。")
                        print(f"    > 新均價: ${new_cost_basis.quantize(CENTS, rounding=ROUND_HALF_UP):,}，新持有: {new_size:.0f} 股")

                    else:
                        # 首次買入
                        portfolio[ticker] = {
                            'size': size_to_buy,
                            'cost_basis': buy_price,
                            'total_cost': actual_cost_of_buy
                        }
                        print(f"  > [買入完成] {ticker}: 投入 ${actual_cost_of_buy.quantize(CENTS, rounding=ROUND_HALF_UP):,} 購買 {size_to_buy:.0f} 股 @ ${buy_price:,.2f}。")

            # 如果當天分配後有剩餘（例如 num_buys=0 但 cash>0），則加回
            # 在這個邏輯中，cash 在分配時已設為 0，所以買入後現金必為 0
            print(f"  > 買入後剩餘現金: ${cash.quantize(CENTS, rounding=ROUND_HALF_UP):,}")

        print("-" * 30)

        # --- 處理當天的所有賣出訊號 (action == -1) ---
        sell_signals = day_trades[day_trades['action'] == -1]
        for _, row in sell_signals.iterrows():
            ticker = row['ticker']
            sell_price = Decimal(str(row['price']))

            if ticker in portfolio:
                position = portfolio[ticker]
                size_held = position['size']
                cash_received = size_held * sell_price
                print(f"{date_str} [賣出訊號] {ticker}:")
                print(f"  > 賣出訊號 {size_held:.4f} 股 @ ${sell_price:,.2f}，獲得 ${cash_received.quantize(CENTS, rounding=ROUND_HALF_UP):,}")

            else:
                print(f"{date_str} [賣出訊號] {ticker}: 投資組合中無此股票，忽略。")
        if show_non_executed_orders:
            sell_signals = day_trades[day_trades['action'] == -3]
            for _, row in sell_signals.iterrows():
                ticker = row['ticker']
                sell_price = Decimal(str(row['price']))
                print(f"{date_str} [無執行賣出訊號] {ticker}: ${sell_price:,.2f}")



        # --- 處理當天的所有買入訊號 (action == 1) ---
        buys_signals = day_trades[day_trades['action'] == 1]
        num_buysignals = len(buys_signals)

        if num_buysignals > 0:

            cash_per_buy = cash / Decimal(num_buysignals)

            print(f"{date_str} [買入訊號] {num_buysignals} 個。可用現金 ${cash.quantize(CENTS, rounding=ROUND_HALF_UP):,}，每個訊號分配 ${cash_per_buy.quantize(CENTS, rounding=ROUND_HALF_UP):,}")
            for _, row in buys_signals.iterrows():
                stop_loss = row.get('stop_loss', None)
                buy_price = Decimal(str(row['price']))
                ticker = row['ticker']

                if buy_price > 0:
                    # 分配的現金即為此次購買的成本
                    size_to_buy = (cash_per_buy / buy_price).to_integral_value(rounding=ROUND_FLOOR)
                    actual_cost_of_buy = size_to_buy * buy_price
                    print(f"  > [買入訊號] {ticker}: 投入 ${actual_cost_of_buy.quantize(CENTS, rounding=ROUND_HALF_UP):,} 購買 {size_to_buy:.0f} 股 @ ${buy_price:,.2f}, 觸發 {row.get('trigger', None): .2f}, 停損 {stop_loss: .2f}。")

        if show_non_executed_orders:
            buys_signals = day_trades[day_trades['action'] == 3]
            for _, row in buys_signals.iterrows():
                ticker = row['ticker']
                buy_price = Decimal(str(row['price']))
                print(f"{date_str} [無執行買入訊號] {ticker}: ${buy_price:,.2f} 觸發 {row.get('trigger', None): .2f} 停損 {row.get('stop_loss', None): .2f}。")

        # Settle funds from today's sales for use on the next day
        cash += pending_settlement

    print("\n--- 模擬結束 ---")

    # 3. --- 計算最終結餘 ---
    final_portfolio_value = Decimal('0.0')
    print("\n最終持股 (以成本價計算):")
    if not portfolio:
        print("  (無)")

    for ticker, position in portfolio.items():
        size = position['size']
        # 根據您的要求，使用 "當初購買的價格" (即平均成本) 來統計價值
        cost_basis = position['cost_basis']
        value_at_cost = size * cost_basis # 這等同於 total_cost

        final_portfolio_value += value_at_cost
        print(f"  > {ticker}: {size:.0f} 股 @ 成本 ${cost_basis.quantize(CENTS, rounding=ROUND_HALF_UP):,} = 總成本價值 ${value_at_cost.quantize(CENTS, rounding=ROUND_HALF_UP):,}")

    final_total_balance = cash + final_portfolio_value

    print("\n--- 最終結算 ---")
    print(f"初始資金: \t${Decimal(str(initial_capital)).quantize(CENTS, rounding=ROUND_HALF_UP):,}")
    print(f"最終剩餘現金: \t${cash.quantize(CENTS, rounding=ROUND_HALF_UP):,}")
    print(f"最終持股價值(成本): ${final_portfolio_value.quantize(CENTS, rounding=ROUND_HALF_UP):,}")
    print(f"最終總結餘: \t${final_total_balance.quantize(CENTS, rounding=ROUND_HALF_UP):,}")

    return final_total_balance



def simulate():
    """
    從命令列執行交易模擬。
    """
    parser = argparse.ArgumentParser(description="根據 JSON 訊號檔案模擬交易")

    parser.add_argument(
        "--file-path",
        type=str,
        default='output/best_strategy_trades.json',
        help="包含交易訊號的 JSON 檔案路徑 (預設: output/best_strategy_trades.json)"
    )

    parser.add_argument(
        "--initial-capital",
        type=float,
        default=10000.0,
        help="模擬的初始資金 (預設: 10000.0)"
    )

    parser.add_argument(
        "--show-none-execute-order",
        action='store_true',
        help="如果設定此旗標，將會顯示 '無執行' 的買入/賣出訊號 (action 3, -3)。"
    )

    args = parser.parse_args()

    # 呼叫 simulate_trades 並傳入所有來自命令列的參數
    simulate_trades(
        file_path=args.file_path,
        initial_capital=args.initial_capital,
        show_non_executed_orders=args.show_none_execute_order
    )
