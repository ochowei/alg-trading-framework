import pandas as pd
from decimal import Decimal, ROUND_HALF_UP, ROUND_FLOOR
import click
from rich import print
from rich.table import Table
from prompt_toolkit import prompt
from prompt_toolkit.completion import PathCompleter
from abc import ABC, abstractmethod
from .models import StrategySignal
from typing import List, Dict
from collections import defaultdict


class SimulationStrategy(ABC):
    """
    Abstract base class for a simulation strategy.
    """
    def __init__(self, initial_capital, show_non_executed_orders=False):
        self.initial_capital = Decimal(str(initial_capital))
        self.show_non_executed_orders = show_non_executed_orders
        self.cash = self.initial_capital
        self.portfolio = {}
        self.CENTS = Decimal('0.01')

    @abstractmethod
    def run_simulation(self, signals: List[StrategySignal]):
        """
        Run the simulation loop. This method must be implemented by subclasses.
        """
        pass

    def _print_final_summary(self):
        """
        Calculates and prints the final portfolio balance and summary.
        """
        print("\n--- 模擬結束 ---")
        final_portfolio_value = Decimal('0.0')

        table = Table(title="最終結算", show_header=True, header_style="bold magenta")
        table.add_column("項目", style="dim", width=20)
        table.add_column("金額", justify="right")

        table.add_row("初始資金", f"${self.initial_capital.quantize(self.CENTS, rounding=ROUND_HALF_UP):,}")

        if self.portfolio:
            holdings_table = Table(title="最終持股 (以成本價計算)", show_header=True, header_style="bold blue")
            holdings_table.add_column("股票代碼", style="cyan")
            holdings_table.add_column("持有股數", justify="right")
            holdings_table.add_column("平均成本", justify="right")
            holdings_table.add_column("總成本價值", justify="right")

            for ticker, position in self.portfolio.items():
                size = position['size']
                cost_basis = position['cost_basis']
                value_at_cost = size * cost_basis
                final_portfolio_value += value_at_cost
                holdings_table.add_row(
                    ticker,
                    f"{size:.0f}",
                    f"${cost_basis.quantize(self.CENTS, rounding=ROUND_HALF_UP):,}",
                    f"${value_at_cost.quantize(self.CENTS, rounding=ROUND_HALF_UP):,}"
                )
            print(holdings_table)

        final_total_balance = self.cash + final_portfolio_value

        table.add_row("最終剩餘現金", f"${self.cash.quantize(self.CENTS, rounding=ROUND_HALF_UP):,}")
        table.add_row("最終持股價值(成本)", f"${final_portfolio_value.quantize(self.CENTS, rounding=ROUND_HALF_UP):,}")
        table.add_row("最終總結餘", f"[bold]${final_total_balance.quantize(self.CENTS, rounding=ROUND_HALF_UP):,}[/bold]")

        print(table)
        return final_total_balance


class Mode1Strategy(SimulationStrategy):
    """
    實作模式 1 的模擬邏輯（預設）。
    - 訊號（Action 2, -2）在 T 日產生，並在 T 日以 T 日的價格執行。
    - 買入（2）：將所有可用現金平均分配，用於買入訊號股。
    - 賣出（-2）：賣出訊號股的所有持股。
    """
    def run_simulation(self, signals: List[StrategySignal]):
        print("--- 模擬開始 (Mode: 1) ---")
        print(f"初始資金: ${self.cash.quantize(self.CENTS, rounding=ROUND_HALF_UP):,}")
        print("-" * 30)

        signals_by_date: Dict[str, List[StrategySignal]] = defaultdict(list)
        for sig in signals:
            signals_by_date[sig.date].append(sig)

        unique_dates = sorted(signals_by_date.keys())

        for date_str in unique_dates:
            current_day_signals = signals_by_date.get(date_str, [])
            pending_settlement = Decimal('0.0')

            # --- Mode 1: Sell logic ---
            sells = [sig for sig in current_day_signals if sig.action == -2]
            for sell_signal in sells:
                ticker = sell_signal.ticker
                sell_price = Decimal(str(sell_signal.price))
                if ticker in self.portfolio:
                    position = self.portfolio.pop(ticker)
                    size_held = position['size']
                    cash_received = size_held * sell_price
                    pending_settlement += cash_received
                    print(f"{date_str} [bold red]賣出完成[/bold red] {ticker}: (Action: {sell_signal.action} from {date_str})")
                    print(f"  > 賣出完成 {size_held:.4f} 股 @ ${sell_price:,.2f}，獲得 ${cash_received.quantize(self.CENTS, rounding=ROUND_HALF_UP):,}")

            # --- Mode 1: Buy logic ---
            buys = [sig for sig in current_day_signals if sig.action == 2]
            num_buys = len(buys)
            if num_buys > 0 and self.cash > Decimal('0.01'):
                cash_per_buy = self.cash / Decimal(num_buys)
                print(f"{date_str} [bold green]買入準備[/bold green] {num_buys} 個。可用現金 ${self.cash.quantize(self.CENTS, rounding=ROUND_HALF_UP):,}，每個訊號分配 ${cash_per_buy.quantize(self.CENTS, rounding=ROUND_HALF_UP):,}")
                self.cash = Decimal('0.0')

                for buy_signal in buys:
                    ticker = buy_signal.ticker
                    buy_price = Decimal(str(buy_signal.price))
                    if buy_price > 0 and cash_per_buy > 0:
                        size_to_buy = (cash_per_buy / buy_price).to_integral_value(rounding=ROUND_FLOOR)
                        if size_to_buy <= 0:
                            self.cash += cash_per_buy
                            continue

                        actual_cost = size_to_buy * buy_price
                        unspent = cash_per_buy - actual_cost
                        self.cash += unspent

                        if ticker in self.portfolio:
                            old_size = self.portfolio[ticker]['size']
                            old_total_cost = self.portfolio[ticker]['total_cost']
                            new_total_cost = old_total_cost + actual_cost
                            new_size = old_size + size_to_buy
                            self.portfolio[ticker] = {
                                'size': new_size,
                                'cost_basis': new_total_cost / new_size,
                                'total_cost': new_total_cost
                            }
                        else:
                            self.portfolio[ticker] = {
                                'size': size_to_buy,
                                'cost_basis': buy_price,
                                'total_cost': actual_cost
                            }
                        print(f"  > [bold green]買入完成[/bold green] {ticker}: (Action: {buy_signal.action} from {date_str}) 投入 ${actual_cost.quantize(self.CENTS, rounding=ROUND_HALF_UP):,} 購買 {size_to_buy:.0f} 股 @ ${buy_price:,.2f}")

            # --- Mode 1: Non-executed orders ---
            if self.show_non_executed_orders:
                sell_signals = [sig for sig in current_day_signals if sig.action == -1]
                for sell_signal in sell_signals:
                    ticker = sell_signal.ticker
                    sell_price = Decimal(str(sell_signal.price))
                    if ticker in self.portfolio:
                        position = self.portfolio[ticker]
                        size_held = position['size']
                        cash_received = size_held * sell_price
                        print(f"{date_str} [yellow]賣出訊號 (M1)[/yellow] {ticker}:")
                        print(f"  > 訊號 {size_held:.4f} 股 @ ${sell_price:,.2f}，可獲得 ${cash_received.quantize(self.CENTS, rounding=ROUND_HALF_UP):,}")
                    else:
                        print(f"{date_str} [yellow]賣出訊號 (M1)[/yellow] {ticker}: 投資組合中無此股票，忽略。")

                sell_signals_ignored = [sig for sig in current_day_signals if sig.action == -3]
                for sell_signal in sell_signals_ignored:
                    ticker = sell_signal.ticker
                    sell_price = Decimal(str(sell_signal.price))
                    print(f"{date_str} [yellow]無執行賣出訊號 (M1)[/yellow] {ticker}: ${sell_price:,.2f}")

                buys_signals = [sig for sig in current_day_signals if sig.action == 1]
                num_buysignals = len(buys_signals)
                if num_buysignals > 0:
                    print(f"{date_str} [cyan]買入訊號 (M1)[/cyan] {num_buysignals} 個。")
                    for buy_signal in buys_signals:
                        ticker = buy_signal.ticker
                        buy_price = Decimal(str(buy_signal.price))
                        print(f"  > [cyan]買入訊號 (M1)[/cyan] {ticker}: @ ${buy_price:,.2f}, 觸發 {buy_signal.trigger or 'N/A'}, 停損 {buy_signal.stop_loss or 'N/A'}")

                buys_signals_ignored = [sig for sig in current_day_signals if sig.action == 3]
                for buy_signal in buys_signals_ignored:
                    ticker = buy_signal.ticker
                    buy_price = Decimal(str(buy_signal.price))
                    print(f"{date_str} [cyan]無執行買入訊號 (M1)[/cyan] {ticker}: ${buy_price:,.2f} 觸發 {buy_signal.trigger or 'N/A'} 停損 {buy_signal.stop_loss or 'N/A'}")

            self.cash += pending_settlement

        return self._print_final_summary()


class Mode2Strategy(SimulationStrategy):
    """
    實作模式 2 的模擬邏輯。
    - 訊號（Action 1, 3, -1, -3）在 T-1 日產生，並在 T 日執行。
    - 使用 T-1 日訊號中的價格作為 T 日的執行價格。
    - 買入（1, 3）：將 T 日的所有可用現金平均分配，用於買入 T-1 日的訊號股。
    - 賣出（-1, -3）：賣出 T-1 日訊號股的所有持股。
    """
    def run_simulation(self, signals: List[StrategySignal]):
        print("--- 模擬開始 (Mode: 2) ---")
        print(f"初始資金: ${self.cash.quantize(self.CENTS, rounding=ROUND_HALF_UP):,}")
        print("-" * 30)

        signals_by_date: Dict[str, List[StrategySignal]] = defaultdict(list)
        for sig in signals:
            signals_by_date[sig.date].append(sig)

        unique_dates = sorted(signals_by_date.keys())

        previous_date = None

        for date_str in unique_dates:
            current_day_signals = signals_by_date.get(date_str, [])
            previous_day_signals = signals_by_date.get(previous_date, []) if previous_date else []
            pending_settlement = Decimal('0.0')

            # --- Mode 2: Sell logic ---
            sells = [sig for sig in previous_day_signals if sig.action in [-1, -3]]
            for sell_signal in sells:
                ticker = sell_signal.ticker
                sell_price = Decimal(str(sell_signal.price))
                if ticker in self.portfolio:
                    position = self.portfolio.pop(ticker)
                    size_held = position['size']
                    cash_received = size_held * sell_price
                    pending_settlement += cash_received
                    signal_date_str = sell_signal.date
                    print(f"{date_str} [bold red]賣出完成[/bold red] {ticker}: (Action: {sell_signal.action} from {signal_date_str})")
                    print(f"  > 賣出完成 {size_held:.4f} 股 @ ${sell_price:,.2f}，獲得 ${cash_received.quantize(self.CENTS, rounding=ROUND_HALF_UP):,}")

            # --- Mode 2: Buy logic ---
            buys = [sig for sig in previous_day_signals if sig.action in [1, 3]]
            num_buys = len(buys)
            if num_buys > 0 and self.cash > Decimal('0.01'):
                cash_per_buy = self.cash / Decimal(num_buys)
                print(f"{date_str} [bold green]買入準備[/bold green] {num_buys} 個。可用現金 ${self.cash.quantize(self.CENTS, rounding=ROUND_HALF_UP):,}，每個訊號分配 ${cash_per_buy.quantize(self.CENTS, rounding=ROUND_HALF_UP):,}")
                self.cash = Decimal('0.0')

                for buy_signal in buys:
                    ticker = buy_signal.ticker
                    buy_price = Decimal(str(buy_signal.price))
                    signal_date_str = buy_signal.date
                    if buy_price > 0 and cash_per_buy > 0:
                        size_to_buy = (cash_per_buy / buy_price).to_integral_value(rounding=ROUND_FLOOR)
                        if size_to_buy <= 0:
                            self.cash += cash_per_buy
                            continue

                        actual_cost = size_to_buy * buy_price
                        unspent = cash_per_buy - actual_cost
                        self.cash += unspent

                        if ticker in self.portfolio:
                            old_size = self.portfolio[ticker]['size']
                            old_total_cost = self.portfolio[ticker]['total_cost']
                            new_total_cost = old_total_cost + actual_cost
                            new_size = old_size + size_to_buy
                            self.portfolio[ticker] = {
                                'size': new_size,
                                'cost_basis': new_total_cost / new_size,
                                'total_cost': new_total_cost
                            }
                        else:
                            self.portfolio[ticker] = {
                                'size': size_to_buy,
                                'cost_basis': buy_price,
                                'total_cost': actual_cost
                            }
                        print(f"  > [bold green]買入完成[/bold green] {ticker}: (Action: {buy_signal.action} from {signal_date_str}) 投入 ${actual_cost.quantize(self.CENTS, rounding=ROUND_HALF_UP):,} 購買 {size_to_buy:.0f} 股 @ ${buy_price:,.2f}")

            # --- Mode 2: Non-executed orders ---
            if self.show_non_executed_orders:
                sell_signals_ignored = [sig for sig in current_day_signals if sig.action == -2]
                for sell_signal in sell_signals_ignored:
                    ticker = sell_signal.ticker
                    sell_price = Decimal(str(sell_signal.price))
                    print(f"{date_str} [yellow]無執行賣出訊號 (M2)[/yellow] {ticker}: ${sell_price:,.2f}")

                buys_signals_ignored = [sig for sig in current_day_signals if sig.action == 2]
                for buy_signal in buys_signals_ignored:
                    ticker = buy_signal.ticker
                    buy_price = Decimal(str(buy_signal.price))
                    print(f"{date_str} [cyan]無執行買入訊號 (M2)[/cyan] {ticker}: ${buy_price:,.2f}")

                sell_signals = [sig for sig in current_day_signals if sig.action == -1]
                sell_signals_3 = [sig for sig in current_day_signals if sig.action == -3]
                buys_signals = [sig for sig in current_day_signals if sig.action == 1]
                buys_signals_3 = [sig for sig in current_day_signals if sig.action == 3]

                if sell_signals or sell_signals_3 or buys_signals or buys_signals_3:
                    print(f"{date_str} [dim] --- Mode 2 T日訊號 (將於 T+1 執行) --- [/dim]")
                    
                    for sell_signal in sell_signals:
                        ticker = sell_signal.ticker
                        sell_price = Decimal(str(sell_signal.price))
                        print(f"{date_str} [magenta]T日賣出訊號 (-1)[/magenta] {ticker}: @ ${sell_price:,.2f}")

                    for sell_signal in sell_signals_3:
                        ticker = sell_signal.ticker
                        sell_price = Decimal(str(sell_signal.price))
                        print(f"{date_str} [magenta]T日賣出訊號 (-3)[/magenta] {ticker}: ${sell_price:,.2f}")

                    for buy_signal in buys_signals:
                        ticker = buy_signal.ticker
                        buy_price = Decimal(str(buy_signal.price))
                        print(f"{date_str} [blue]T日買入訊號 (1)[/blue] {ticker}: @ ${buy_price:,.2f}, 觸發 {buy_signal.trigger or 'N/A'}, 停損 {buy_signal.stop_loss or 'N/A'}")

                    for buy_signal in buys_signals_3:
                        ticker = buy_signal.ticker
                        buy_price = Decimal(str(buy_signal.price))
                        print(f"{date_str} [blue]T日買入訊號 (3)[/blue] {ticker}: @ ${buy_price:,.2f} 觸發 {buy_signal.trigger or 'N/A'} 停損 {buy_signal.stop_loss or 'N/A'}")

            self.cash += pending_settlement
            previous_date = date_str

        return self._print_final_summary()


def simulate_trades(file_path, initial_capital, show_non_executed_orders=False, mode=1):
    """
    根據給定的模式，作為工廠選擇並執行交易模擬策略。

    此函數讀取包含交易訊號的 JSON 檔案，按日期排序，
    然後將模擬委託給特定的策略類別（`Mode1Strategy` 或 `Mode2Strategy`）。

    Args:
        file_path (str): 包含交易訊號的 JSON 檔案路徑。
        initial_capital (float or str): 模擬的初始資金。
        show_non_executed_orders (bool): 如果為 True，則會印出未執行的訊號。
        mode (int): 要使用的模擬模式（1 或 2）。

    Returns:
        Decimal: 投資組合的最終總餘額。
    """
    try:
        df = pd.read_json(file_path)
    except Exception as e:
        print(f"Error reading JSON file: {e}")
        return

    df['date'] = pd.to_datetime(df['date'])
    df = df.sort_values(by='date')

    signals_list = [
        StrategySignal(
            date=row['date'].strftime('%Y-%m-%d'),
            ticker=row['ticker'],
            action=row['action'],
            size=row['size'],
            price=row['price'],
            total=row['total'],
            trigger=row.get('trigger'),
            stop_loss=row.get('stop_loss'),
            stop_loss_trigger=row.get('stop_loss_trigger'),
            pnl=row.get('pnl')
        ) for _, row in df.iterrows()
    ]

    strategy: SimulationStrategy
    if mode == 1:
        strategy = Mode1Strategy(initial_capital, show_non_executed_orders)
    elif mode == 2:
        strategy = Mode2Strategy(initial_capital, show_non_executed_orders)
    else:
        print(f"Error: Invalid mode '{mode}'. Please use 1 or 2.")
        return

    return strategy.run_simulation(signals_list)

@click.command()
@click.option(
    "--file-path",
    type=click.Path(exists=True, dir_okay=False, readable=True),
    default='output/strategy_trades.json',
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
@click.option(
    "--mode",
    type=click.IntRange(1, 2), # 限制 mode 只能是 1 或 2
    default=1,
    help="模擬模式 (1: T日執行 2/-2, 2: T日執行 T-1日的 1/3/-1/-3)。"
)
def simulate(file_path, initial_capital, show_none_execute_order, mode):
    """
    從命令列執行交易模擬。
    """
    if file_path is None:
        file_path = prompt(
            "請輸入 JSON 檔案路徑: ",
            completer=PathCompleter(),
            default='output/strategy_trades.json'
        )
        initial_capital = click.prompt("請輸入初始資金", type=float, default=10000.0)
        show_none_execute_order = click.confirm("是否顯示 '無執行' 的買入/賣出訊號?", default=True)
        mode = click.prompt("請輸入模擬模式 (1: T日執行 2/-2, 2: T日執行 T-1日的 1/3/-1/-3)", type=click.IntRange(1, 2), default=1)


    # If initial_capital is still None, it means file_path was provided, but not this.
    # We should prompt for it.
    if initial_capital is None:
        initial_capital = 10000.0
    
    # We added mode, but if file_path was provided, mode will be its default (1)
    # unless specified via --mode. This is correct behavior.

    simulate_trades(
        file_path=file_path,
        initial_capital=initial_capital,
        show_non_executed_orders=show_none_execute_order,
        mode=mode
    )