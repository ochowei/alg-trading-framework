from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from workflow import main as opt_strategy
from run_strategy import run_strategy_cli
from sj_trading.simulation import simulate

def main():
    """
    Displays the main menu and executes the selected workflow.
    """
    console = Console()

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
                opt_strategy()
            except SystemExit:
                pass
            except Exception as e:
                console.print(f"[bold red]執行策略優化時發生錯誤：{e}[/bold red]")
        elif choice == "2":
            console.print("\n[bold yellow]執行策略回測...[/bold yellow]\n")
            try:
                run_strategy_cli()
            except SystemExit:
                pass
            except Exception as e:
                console.print(f"[bold red]執行策略回測時發生錯誤：{e}[/bold red]")
        elif choice == "3":
            console.print("\n[bold yellow]執行交易模擬...[/bold yellow]\n")
            try:
                simulate()
            except SystemExit:
                pass
            except Exception as e:
                console.print(f"[bold red]執行交易模擬時發生錯誤：{e}[/bold red]")
        elif choice == "4":
            console.print("\n[bold]程式結束。[/bold]\n")
            break

if __name__ == "__main__":
    main()
