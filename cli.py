"""
Interactive Command-Line Interface for OmniTrace.
Provides live ReAct step-by-step reasoning trace visualization using Rich.
"""

import sys
import time
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
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
[dim]Autonomous Hybrid Intelligence Engine (SQL + Script RAG)[/dim]
"""

def print_trace(trace):
    """Renders the step-by-step ReAct reasoning steps and final synthesis."""
    console.print()
    console.print(f"[bold yellow]=== Reasoning Chain ({len(trace.steps)} turns, {trace.execution_time_sec}s) ===[/bold yellow]")

    for step in trace.steps:
        # Step Panel
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
            content.append("[bold green]Self-Healing Recovery:[/bold green] Successfully recovered from prior error!")

        panel = Panel("\n".join(content), title=f"Step {step.step_number}", border_style="cyan")
        console.print(panel)

    console.print()
    console.print(Panel(Markdown(trace.final_answer), title="[bold green]Final Synthesized Diagnosis[/bold green]", border_style="green"))
    console.print(f"[dim]Tools Invoked: {', '.join(trace.tools_called) or 'None'} | Status: {trace.status} | Latency: {trace.execution_time_sec}s[/dim]\n")

def main():
    console.clear()
    console.print(BANNER)
    console.print(f"[bold green]Initializing OmniTrace Agent (Provider: {DEFAULT_PROVIDER})...[/bold green]")
    
    try:
        agent = OmniTraceAgent()
        console.print(f"[dim]Active Model: {agent.model_name}[/dim]\n")
    except Exception as e:
        console.print(f"[bold red]Initialization Error:[/bold red] {e}")
        sys.exit(1)

    console.print("[yellow]Type your analytical question (or 'exit' to quit):[/yellow]\n")

    # Sample prompt suggestions
    console.print("[dim]Suggested Queries:")
    console.print(" 1. Which episode in Bhaichara had the highest audience drop-off rate, and what was happening in the script during that scene?")
    console.print(" 2. What is the viewer share and average rating of Bhaichara in Haryana compared to Delhi-NCR?")
    console.print(" 3. Why did viewers drop off at 18:45 in Episode 1 of Dopamine Hustle?[/dim]\n")

    while True:
        try:
            query = Prompt.ask("[bold cyan]OmniTrace >[/bold cyan]")
            if not query or not query.strip():
                continue
            if query.strip().lower() in ("exit", "quit", "q"):
                console.print("[green]Goodbye![/green]")
                break

            with console.status("[bold green]Executing ReAct loop (Reasoning & Tool Invocations)...[/bold green]"):
                trace = agent.run(query)

            print_trace(trace)

        except KeyboardInterrupt:
            console.print("\n[yellow]Session interrupted. Exiting.[/yellow]")
            break
        except Exception as e:
            console.print(f"[bold red]Runtime Error:[/bold red] {e}\n")

if __name__ == "__main__":
    main()
