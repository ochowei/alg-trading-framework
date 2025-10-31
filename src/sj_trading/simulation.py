import pandas as pd
from decimal import Decimal, ROUND_HALF_UP, ROUND_FLOOR
import click
from rich import print
from rich.table import Table
from prompt_toolkit import prompt
from prompt_toolkit.completion import PathCompleter

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
        print("-" * 30 + f" {pd.to_datetime(date).date()} " + "-" * 30)

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

                print(f"{date_str} [bold red]賣出完成[/bold red] {ticker}:")
                print(f"  > 賣出完成 {size_held:.4f} 股 @ ${sell_price:,.2f}，獲得 ${cash_received.quantize(CENTS, rounding=ROUND_HALF_UP):,}")
                print(f"  > 目前現金: ${cash.quantize(CENTS, rounding=ROUND_HALF_UP):,}")

        # 2. --- 處理當天的所有買入 (action == 2) ---
        buys = day_trades[day_trades['action'] == 2]
        num_buys = len(buys)

        if num_buys > 0 and cash > Decimal('0.01'): # 確保有現金且有買入訊號
            cash_per_buy = cash / Decimal(num_buys)

            print(f"{date_str} [bold green]買入準備[/bold green] {num_buys} 個。可用現金 ${cash.quantize(CENTS, rounding=ROUND_HALF_UP):,}，每個訊號分配 ${cash_per_buy.quantize(CENTS, rounding=ROUND_HALF_UP):,}")

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
                        print(f"  > [bold green]加倉完成[/bold green] {ticker}: 投入 ${actual_cost_of_buy.quantize(CENTS, rounding=ROUND_HALF_UP):,} 購買 {size_to_buy:.0f} 股 @ ${buy_price:,.2f}。")
                        print(f"    > 新均價: ${new_cost_basis.quantize(CENTS, rounding=ROUND_HALF_UP):,}，新持有: {new_size:.0f} 股")

                    else:
                        # 首次買入
                        portfolio[ticker] = {
                            'size': size_to_buy,
                            'cost_basis': buy_price,
                            'total_cost': actual_cost_of_buy
                        }
                        print(f"  > [bold green]買入完成[/bold green] {ticker}: 投入 ${actual_cost_of_buy.quantize(CENTS, rounding=ROUND_HALF_UP):,} 購買 {size_to_buy:.0f} 股 @ ${buy_price:,.2f}。")
            print(f"  > 買入後剩餘現金: ${cash.quantize(CENTS, rounding=ROUND_HALF_UP):,}")

        # --- 處理當天的所有賣出訊號 (action == -1) ---
        if show_non_executed_orders:
            sell_signals = day_trades[day_trades['action'] == -1]
            for _, row in sell_signals.iterrows():
                ticker = row['ticker']
                sell_price = Decimal(str(row['price']))
                if ticker in portfolio:
                    position = portfolio[ticker]
                    size_held = position['size']
                    cash_received = size_held * sell_price
                    print(f"{date_str} [yellow]賣出訊號[/yellow] {ticker}:")
                    print(f"  > 訊號 {size_held:.4f} 股 @ ${sell_price:,.2f}，可獲得 ${cash_received.quantize(CENTS, rounding=ROUND_HALF_UP):,}")
                else:
                    print(f"{date_str} [yellow]賣出訊號[/yellow] {ticker}: 投資組合中無此股票，忽略。")

            sell_signals_ignored = day_trades[day_trades['action'] == -3]
            for _, row in sell_signals_ignored.iterrows():
                ticker = row['ticker']
                sell_price = Decimal(str(row['price']))
                print(f"{date_str} [yellow]無執行賣出訊號[/yellow] {ticker}: ${sell_price:,.2f}")

        # --- 處理當天的所有買入訊號 (action == 1) ---
        if show_non_executed_orders:
            buys_signals = day_trades[day_trades['action'] == 1]
            num_buysignals = len(buys_signals)
            if num_buysignals > 0:
                print(f"{date_str} [cyan]買入訊號[/cyan] {num_buysignals} 個。")
                for _, row in buys_signals.iterrows():
                    ticker = row['ticker']
                    buy_price = Decimal(str(row['price']))
                    print(f"  > [cyan]買入訊號[/cyan] {ticker}: @ ${buy_price:,.2f}, 觸發 {row.get('trigger', 'N/A')}, 停損 {row.get('stop_loss', 'N/A')}")

            buys_signals_ignored = day_trades[day_trades['action'] == 3]
            for _, row in buys_signals_ignored.iterrows():
                ticker = row['ticker']
                buy_price = Decimal(str(row['price']))
                print(f"{date_str} [cyan]無執行買入訊號[/cyan] {ticker}: ${buy_price:,.2f} 觸發 {row.get('trigger', 'N/A')} 停損 {row.get('stop_loss', 'N/A')}")

        # Settle funds from today's sales for use on the next day
        cash += pending_settlement

    print("\n--- 模擬結束 ---")

    # 3. --- 計算最終結餘 ---
    final_portfolio_value = Decimal('0.0')

    table = Table(title="最終結算", show_header=True, header_style="bold magenta")
    table.add_column("項目", style="dim", width=20)
    table.add_column("金額", justify="right")

    table.add_row("初始資金", f"${Decimal(str(initial_capital)).quantize(CENTS, rounding=ROUND_HALF_UP):,}")

    if portfolio:
        holdings_table = Table(title="最終持股 (以成本價計算)", show_header=True, header_style="bold blue")
        holdings_table.add_column("股票代碼", style="cyan")
        holdings_table.add_column("持有股數", justify="right")
        holdings_table.add_column("平均成本", justify="right")
        holdings_table.add_column("總成本價值", justify="right")

        for ticker, position in portfolio.items():
            size = position['size']
            cost_basis = position['cost_basis']
            value_at_cost = size * cost_basis
            final_portfolio_value += value_at_cost
            holdings_table.add_row(
                ticker,
                f"{size:.0f}",
                f"${cost_basis.quantize(CENTS, rounding=ROUND_HALF_UP):,}",
                f"${value_at_cost.quantize(CENTS, rounding=ROUND_HALF_UP):,}"
            )
        print(holdings_table)

    final_total_balance = cash + final_portfolio_value

    table.add_row("最終剩餘現金", f"${cash.quantize(CENTS, rounding=ROUND_HALF_UP):,}")
    table.add_row("最終持股價值(成本)", f"${final_portfolio_value.quantize(CENTS, rounding=ROUND_HALF_UP):,}")
    table.add_row("最終總結餘", f"[bold]${final_total_balance.quantize(CENTS, rounding=ROUND_HALF_UP):,}[/bold]")

    print(table)

    return final_total_balance

@click.command()
@click.option(
    "--file-path",
    type=click.Path(exists=True, dir_okay=False, readable=True),
    default=None,
    help="包含交易訊號的 JSON 檔案路徑。"
)
@click.option(
    "--initial-capital",
    type=float,
    default=None,
    help="模擬的初始資金。"
)
@click.option(
    "--show-none-execute-order",
    is_flag=True,
    help="如果設定此旗標，將會顯示 '無執行' 的買入/賣出訊號。"
)
def simulate(file_path, initial_capital, show_none_execute_order):
    """
    從命令列執行交易模擬。
    """
    if file_path is None:
        file_path = prompt(
            "請輸入 JSON 檔案路徑: ",
            completer=PathCompleter(),
            default='output/best_strategy_trades.json'
        )
        initial_capital = click.prompt("請輸入初始資金", type=float, default=10000.0)
        show_none_execute_order = click.confirm("是否顯示 '無執行' 的買入/賣出訊號?", default=False)


    # If initial_capital is still None, it means file_path was provided, but not this.
    # We should prompt for it.
    if initial_capital is None:
        initial_capital = 10000.0

    simulate_trades(
        file_path=file_path,
        initial_capital=initial_capital,
        show_non_executed_orders=show_none_execute_order
    )