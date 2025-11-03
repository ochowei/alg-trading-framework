import click
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from prompt_toolkit import prompt as toolkit_prompt
from prompt_toolkit.completion import PathCompleter
from datetime import datetime, timedelta

# Import the functions from other scripts
from workflow import main as workflow_main, opt_strategy
from run_strategy import run_strategy_logic
from sj_trading.simulation import simulate as simulate_cli
from sj_trading.config import Config

def show_interactive_menu():
    """
    Displays the interactive main menu and executes the selected workflow.
    """
    console = Console()
    path_completer = PathCompleter()

    while True:
        console.print(Panel.fit(
            "[bold cyan]請選擇要執行的工作流程：[/bold cyan]\n\n"
            "[green]1.[/green] 執行策略優化 (Optimize Strategy)\n"
            "[green]2.[/green] 執行策略回測 (Run Strategy)\n"
            "[green]3.[/green] 執行交易模擬 (Simulate Trades)\n"
            "[red]4.[/red] 離開 (Exit)\n",
            title="互動式主選單"
        ))

        choice = Prompt.ask("請輸入選項 [1-4]", choices=["1", "2", "3", "4"], default="4")

        if choice == "1":
            console.print("\n[bold yellow]執行策略優化...[/bold yellow]\n")
            try:
                filename = toolkit_prompt(
                    "請輸入資料檔案路徑: ",
                    completer=path_completer,
                    default=Config.YFINANCE_FILE_NAME
                )
                start_date = Prompt.ask(
                    "請輸入開始日期 (YYYY-MM-DD)",
                    default=(datetime.now() - timedelta(days=365)).strftime('%Y-%m-%d')
                )
                end_date = Prompt.ask(
                    "請輸入結束日期 (YYYY-MM-DD)",
                    default=(datetime.now() + timedelta(days=7)).strftime('%Y-%m-%d')
                )
                opt_strategy(filename=filename, start_date=start_date, end_date=end_date)
            except Exception as e:
                console.print(f"[bold red]執行策略優化時發生錯誤：{e}[/bold red]")
        elif choice == "2":
            console.print("\n[bold yellow]執行策略回測...[/bold yellow]\n")
            try:
                data_file = toolkit_prompt(
                    "請輸入市場數據 CSV 檔案: ",
                    completer=path_completer,
                    default=Config.YFINANCE_FILE_NAME
                )
                input_file = toolkit_prompt(
                    "請輸入策略參數 JSON 檔案: ",
                    completer=path_completer,
                    default="output/best_strategy_params.json"
                )
                output_file = toolkit_prompt(
                    "請輸入儲存交易訊號的 JSON 檔案: ",
                    completer=path_completer,
                    default="output/strategy_trades.json"
                )
                start_date = Prompt.ask("請輸入開始日期 (YYYY-MM-DD) [可選]", default="")
                end_date = Prompt.ask("請輸入結束日期 (YYYY-MM-DD) [可選]", default="")
                skip_dates = Prompt.ask("請輸入要跳過的日期 (YYYY-MM-DD,...) [可選]", default="")

                run_strategy_logic(
                    data_file=data_file,
                    input_file=input_file,
                    output_file=output_file,
                    start_date=start_date if start_date else None,
                    end_date=end_date if end_date else None,
                    skip_dates=skip_dates if skip_dates else None
                )
            except Exception as e:
                console.print(f"[bold red]執行策略回測時發生錯誤：{e}[/bold red]")
        elif choice == "3":
            console.print("\n[bold yellow]執行交易模擬...[/bold yellow]\n")
            try:
                # Let the original click command handle its own prompts
                simulate_cli.main(standalone_mode=False)
            except click.exceptions.Abort:
                 console.print("\n[bold red]操作中止。[/bold red]")
            except Exception as e:
                console.print(f"[bold red]執行交易模擬時發生錯誤：{e}[/bold red]")
        elif choice == "4":
            console.print("\n[bold]程式結束。[/bold]\n")
            break

@click.group(invoke_without_command=True)
@click.pass_context
def cli(ctx):
    """
    一個整合的CLI工具，用於執行交易策略的優化、回測和模擬。
    如果沒有提供子命令，將會顯示一個互動式選單。
    """
    if ctx.invoked_subcommand is None:
        show_interactive_menu()

@cli.command()
@click.option(
    "--filename",
    type=str,
    default=Config.YFINANCE_FILE_NAME,
    help=f"要讀取的 CSV 資料檔案路徑 (預設: {Config.YFINANCE_FILE_NAME})"
)
@click.option(
    "--start-date",
    type=str,
    default=(datetime.now() - timedelta(days=365)).strftime('%Y-%m-%d'),
    help="回測開始日期 (格式: YYYY-MM-DD)"
)
@click.option(
    "--end-date",
    type=str,
    default=(datetime.now() + timedelta(days=7)).strftime('%Y-%m-%d'),
    help="回測結束日期 (格式: YYYY-MM-DD)"
)
def opt(filename, start_date, end_date):
    """執行策略優化"""
    print(f"🔄 開始執行 opt_strategy，使用資料檔案: {filename}, 日期範圍: {start_date} to {end_date}")
    opt_strategy(filename=filename, start_date=start_date, end_date=end_date)

@cli.command()
@click.option(
    "--data-file",
    type=str,
    default=Config.YFINANCE_FILE_NAME,
    help=f"包含市場數據的 CSV 檔案 (預設: {Config.YFINANCE_FILE_NAME})"
)
@click.option(
    "--input-file",
    type=str,
    default="output/best_strategy_params.json",
    help="包含最佳策略參數的 JSON 檔案"
)
@click.option(
    "--output-file",
    type=str,
    default="output/strategy_trades.json",
    help="儲存交易訊號的輸出 JSON 檔案"
)
@click.option("--start-date", type=str, help="覆寫所有策略的開始日期 (YYYY-MM-DD)。")
@click.option("--end-date", type=str, help="覆寫所有策略的結束日期 (YYYY-MM-DD)。")
@click.option("--skip-dates", type=str, help="覆寫所有策略要跳過的日期 (YYYY-MM-DD,YYYY-MM-DD)。")
def run(data_file, input_file, output_file, start_date, end_date, skip_dates):
    """執行策略回測"""
    run_strategy_logic(
        data_file=data_file,
        input_file=input_file,
        output_file=output_file,
        start_date=start_date,
        end_date=end_date,
        skip_dates=skip_dates
    )

cli.add_command(simulate_cli, "sim")

if __name__ == "__main__":
    cli()
