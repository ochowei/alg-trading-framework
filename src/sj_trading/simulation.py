import argparse
import pandas as pd
from decimal import Decimal, ROUND_HALF_UP, ROUND_FLOOR
import click
from rich.console import Console
from rich.table import Table

console = Console()

def simulate_trades(file_path, initial_capital, show_non_executed_orders=False):
    """
    根據用戶指定的規則模擬交易。
    """
    try:
        df = pd.read_json(file_path)
    except Exception as e:
        console.print(f"[bold red]讀取 JSON 檔案時出錯: {e}[/bold red]")
        return

    df['date'] = pd.to_datetime(df['date'])
    df = df.sort_values(by='date')

    cash = Decimal(str(initial_capital))
    portfolio = {}
    ZERO = Decimal('0.00')
    CENTS = Decimal('0.01')

    console.print(f"--- 模擬開始 ---")
    console.print(f"初始資金: [yellow]${cash.quantize(CENTS, rounding=ROUND_HALF_UP):,}[/yellow]")
    console.print("-" * 30)

    unique_dates = df['date'].unique()

    for date in unique_dates:
        console.print("-" * 30 + f" {pd.to_datetime(date).date()} " + "-" * 30)

        day_trades = df[df['date'] == date]
        date_str = str(pd.to_datetime(date).date())
        pending_settlement = Decimal('0.0')

        # 1. --- 處理當天的所有賣出 (action == -2) ---
        sells = day_trades[day_trades['action'] == -2]
        for _, row in sells.iterrows():
            ticker = row['ticker']
            sell_price = Decimal(str(row['price']))

            if ticker in portfolio:
                position = portfolio.pop(ticker)
                size_held = position['size']
                cash_received = size_held * sell_price
                pending_settlement += cash_received

                console.print(f"{date_str} [bold red]賣出完成[/bold red] {ticker}:")
                console.print(f"  > 賣出完成 {size_held:.4f} 股 @ ${sell_price:,.2f}，獲得 ${cash_received.quantize(CENTS, rounding=ROUND_HALF_UP):,}")
                console.print(f"  > 目前現金: ${cash.quantize(CENTS, rounding=ROUND_HALF_UP):,}")

        # 2. --- 處理當天的所有買入 (action == 2) ---
        buys = day_trades[day_trades['action'] == 2]
        num_buys = len(buys)

        if num_buys > 0 and cash > Decimal('0.01'):
            cash_per_buy = cash / Decimal(num_buys)
            console.print(f"{date_str} [bold green]買入分配[/bold green] {num_buys} 個。可用現金 ${cash.quantize(CENTS, rounding=ROUND_HALF_UP):,}，每個訊號分配 ${cash_per_buy.quantize(CENTS, rounding=ROUND_HALF_UP):,}")

            cash = Decimal('0.0')

            for _, row in buys.iterrows():
                ticker = row['ticker']
                buy_price = Decimal(str(row['price']))

                if buy_price > 0 and cash_per_buy > 0:
                    size_to_buy = (cash_per_buy / buy_price).to_integral_value(rounding=ROUND_FLOOR)
                    if size_to_buy <= 0:
                        console.print(f"  > [yellow]買入跳過[/yellow] {ticker}: 分配現金 ${cash_per_buy.quantize(CENTS, rounding=ROUND_HALF_UP):,} 無法購買任何股數 @ ${buy_price:,.2f}。")
                        cash += cash_per_buy
                        continue

                    actual_cost_of_buy = size_to_buy * buy_price
                    unspent_cash = cash_per_buy - actual_cost_of_buy
                    cash += unspent_cash

                    if ticker in portfolio:
                        old_size = portfolio[ticker]['size']
                        old_total_cost = portfolio[ticker]['total_cost']
                        new_total_cost = old_total_cost + actual_cost_of_buy
                        new_size = old_size + size_to_buy
                        new_cost_basis = new_total_cost / new_size
                        portfolio[ticker] = {'size': new_size, 'cost_basis': new_cost_basis, 'total_cost': new_total_cost}
                        console.print(f"  > [bold green]加倉完成[/bold green] {ticker}: 投入 ${actual_cost_of_buy.quantize(CENTS, rounding=ROUND_HALF_UP):,} 購買 {size_to_buy:.0f} 股 @ ${buy_price:,.2f}。")
                        console.print(f"    > 新均價: ${new_cost_basis.quantize(CENTS, rounding=ROUND_HALF_UP):,}，新持有: {new_size:.0f} 股")
                    else:
                        portfolio[ticker] = {'size': size_to_buy, 'cost_basis': buy_price, 'total_cost': actual_cost_of_buy}
                        console.print(f"  > [bold green]買入完成[/bold green] {ticker}: 投入 ${actual_cost_of_buy.quantize(CENTS, rounding=ROUND_HALF_UP):,} 購買 {size_to_buy:.0f} 股 @ ${buy_price:,.2f}。")
            console.print(f"  > 買入後剩餘現金: ${cash.quantize(CENTS, rounding=ROUND_HALF_UP):,}")

        console.print("-" * 30)

        # --- 處理當天的所有賣出訊號 (action == -1) ---
        sell_signals = day_trades[day_trades['action'] == -1]
        for _, row in sell_signals.iterrows():
            ticker = row['ticker']
            sell_price = Decimal(str(row['price']))
            if ticker in portfolio:
                position = portfolio[ticker]
                size_held = position['size']
                cash_received = size_held * sell_price
                console.print(f"{date_str} [yellow]賣出訊號[/yellow] {ticker}:")
                console.print(f"  > 賣出訊號 {size_held:.4f} 股 @ ${sell_price:,.2f}，獲得 ${cash_received.quantize(CENTS, rounding=ROUND_HALF_UP):,}")
            else:
                console.print(f"{date_str} [yellow]賣出訊號[/yellow] {ticker}: 投資組合中無此股票，忽略。")

        if show_non_executed_orders:
            sell_signals = day_trades[day_trades['action'] == -3]
            for _, row in sell_signals.iterrows():
                ticker = row['ticker']
                sell_price = Decimal(str(row['price']))
                console.print(f"{date_str} [dim]無執行賣出訊號[/dim] {ticker}: ${sell_price:,.2f}")

        # --- 處理當天的所有買入訊號 (action == 1) ---
        buys_signals = day_trades[day_trades['action'] == 1]
        num_buysignals = len(buys_signals)
        if num_buysignals > 0:
            cash_per_buy = cash / Decimal(num_buysignals)
            console.print(f"{date_str} [yellow]買入訊號[/yellow] {num_buysignals} 個。可用現金 ${cash.quantize(CENTS, rounding=ROUND_HALF_UP):,}，每個訊號分配 ${cash_per_buy.quantize(CENTS, rounding=ROUND_HALF_UP):,}")
            for _, row in buys_signals.iterrows():
                stop_loss = row.get('stop_loss', None)
                buy_price = Decimal(str(row['price']))
                ticker = row['ticker']
                if buy_price > 0:
                    size_to_buy = (cash_per_buy / buy_price).to_integral_value(rounding=ROUND_FLOOR)
                    actual_cost_of_buy = size_to_buy * buy_price
                    console.print(f"  > [yellow]買入訊號[/yellow] {ticker}: 投入 ${actual_cost_of_buy.quantize(CENTS, rounding=ROUND_HALF_UP):,} 購買 {size_to_buy:.0f} 股 @ ${buy_price:,.2f}, 觸發 {row.get('trigger', None): .2f}, 停損 {stop_loss: .2f}。")

        if show_non_executed_orders:
            buys_signals = day_trades[day_trades['action'] == 3]
            for _, row in buys_signals.iterrows():
                ticker = row['ticker']
                buy_price = Decimal(str(row['price']))
                console.print(f"{date_str} [dim]無執行買入訊號[/dim] {ticker}: ${buy_price:,.2f} 觸發 {row.get('trigger', None): .2f} 停損 {row.get('stop_loss', None): .2f}。")

        cash += pending_settlement

    console.print("\n--- 模擬結束 ---")

    # 3. --- 計算最終結餘 ---
    final_portfolio_value = Decimal('0.0')
    portfolio_table = Table(title="最終持股 (以成本價計算)", show_header=True, header_style="bold magenta")
    portfolio_table.add_column("股票代碼", style="dim", width=12)
    portfolio_table.add_column("持有股數", justify="right")
    portfolio_table.add_column("平均成本", justify="right")
    portfolio_table.add_column("總成本價值", justify="right")

    if not portfolio:
        console.print("  (無)")
    else:
        for ticker, position in portfolio.items():
            size = position['size']
            cost_basis = position['cost_basis']
            value_at_cost = size * cost_basis
            final_portfolio_value += value_at_cost
            portfolio_table.add_row(
                ticker,
                f"{size:.0f}",
                f"${cost_basis.quantize(CENTS, rounding=ROUND_HALF_UP):,}",
                f"${value_at_cost.quantize(CENTS, rounding=ROUND_HALF_UP):,}"
            )
        console.print(portfolio_table)

    final_total_balance = cash + final_portfolio_value

    summary_table = Table(title="[bold]最終結算[/bold]", show_header=False, border_style="blue")
    summary_table.add_column("項目", style="cyan")
    summary_table.add_column("金額", justify="right", style="bold yellow")
    summary_table.add_row("初始資金", f"${Decimal(str(initial_capital)).quantize(CENTS, rounding=ROUND_HALF_UP):,}")
    summary_table.add_row("最終剩餘現金", f"${cash.quantize(CENTS, rounding=ROUND_HALF_UP):,}")
    summary_table.add_row("最終持股價值(成本)", f"${final_portfolio_value.quantize(CENTS, rounding=ROUND_HALF_UP):,}")
    summary_table.add_row("[bold]最終總結餘[/bold]", f"[bold green]${final_total_balance.quantize(CENTS, rounding=ROUND_HALF_UP):,}[/bold green]")
    console.print(summary_table)

    return final_total_balance

@click.command()
@click.option(
    '--file-path',
    prompt='請輸入交易訊號 JSON 檔案路徑',
    default='output/best_strategy_trades.json',
    help='包含交易訊號的 JSON 檔案路徑。'
)
@click.option(
    '--initial-capital',
    prompt='請輸入初始資金',
    default=10000.0,
    type=float,
    help='模擬的初始資金。'
)
@click.option(
    '--show-none-execute-order',
    is_flag=True,
    prompt='是否顯示 "無執行" 的訊號?',
    default=False,
    help='如果設定，將會顯示 "無執行" 的買入/賣出訊號。'
)
def simulate(file_path, initial_capital, show_none_execute_order):
    """
    從命令列執行交易模擬。
    """
    simulate_trades(
        file_path=file_path,
        initial_capital=initial_capital,
        show_non_executed_orders=show_none_execute_order
    )