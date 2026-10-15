import sys
from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown
from rich.prompt import Prompt

from omni_trace.agent import OmniTraceAgent
from omni_trace.config import DEFAULT_PROVIDER

console = Console()

BANNER = """
[bold cyan]  ___                    _ _____                     [/bold cyan]
[bold cyan] / _ \\ _ __ ___  _ __ (_) |_   _| __ __ _  ___ ___   [/bold cyan]
[bold cyan]| | | | '_ ` _ \\| '_ \\| |   | || '__/ _` |/ __/ _ \\  [/bold cyan]
[bold cyan]| |_| | | | | | | | | | |   | || | | (_| | (_|  __/  [/bold cyan]
[bold cyan] \\___/|_| |_| |_|_| |_|_|   |_||_|  \\__,_|\\___\\___|  [/bold cyan]
[dim]Hybrid SQL & Semantic RAG Intelligence Agent[/dim]
"""

def print_trace(trace):
    console.print()
    console.print(f"[bold yellow]=== Reasoning Chain ({len(trace.steps)} turns, {trace.execution_time_sec}s) ===[/bold yellow]")

    for step in trace.steps:
        content = []
        if step.thought:
            content.append(f"[bold blue]Thought:[/bold blue] {step.thought}")
        if step.action:
            args_str = ", ".join(f"{k}={v!r}" for k, v in step.action.tool_args.items())
            content.append(f"[bold magenta]Action:[/bold magenta] [green]{step.action.tool_name}[/green]({args_str})")
        if step.observation:
            obs_preview = step.observation[:250] + ("..." if len(step.observation) > 250 else "")
            content.append(f"[bold dim]Observation:[/bold dim] {obs_preview}")
        if step.self_healed:
            content.append("[bold green]Self-Healing Recovery:[/bold green] Recovered from prior execution error.")

        panel = Panel("\n".join(content), title=f"Step {step.step_number}", border_style="cyan")
        console.print(panel)

    console.print()
    console.print(Panel(Markdown(trace.final_answer), title="[bold green]Diagnosis[/bold green]", border_style="green"))
    console.print(f"[dim]Tools: {', '.join(trace.tools_called) or 'None'} | Status: {trace.status} | Latency: {trace.execution_time_sec}s[/dim]\n")

def main():
    console.clear()
    console.print(BANNER)
    console.print(f"[bold green]Initializing Agent ({DEFAULT_PROVIDER})...[/bold green]")
    
    try:
        agent = OmniTraceAgent()
        console.print(f"[dim]Model: {agent.model_name}[/dim]\n")
    except Exception as e:
        console.print(f"[bold red]Initialization Error:[/bold red] {e}")
        sys.exit(1)

    console.print("[yellow]Enter analytical query ('exit' to quit):[/yellow]\n")

    while True:
        try:
            query = Prompt.ask("[bold cyan]OmniTrace >[/bold cyan]")
            if not query or not query.strip():
                continue
            if query.strip().lower() in ("exit", "quit", "q"):
                console.print("[green]Exited.[/green]")
                break

            with console.status("[bold green]Executing ReAct loop...[/bold green]"):
                trace = agent.run(query)

            print_trace(trace)

        except KeyboardInterrupt:
            console.print("\n[yellow]Interrupted.[/yellow]")
            break
        except Exception as e:
            console.print(f"[bold red]Runtime Error:[/bold red] {e}\n")

if __name__ == "__main__":
    main()
