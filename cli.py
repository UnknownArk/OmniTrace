import sys
import uuid
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt

from omni_trace.graph.workflow import build_incident_graph

console = Console()

BANNER = """
[bold cyan]  ___                    _ _____                     [/bold cyan]
[bold cyan] / _ \\ _ __ ___  _ __ (_) |_   _| __ __ _  ___ ___   [/bold cyan]
[bold cyan]| | | | '_ ` _ \\| '_ \\| |   | || '__/ _` |/ __/ _ \\  [/bold cyan]
[bold cyan]| |_| | | | | | | | | | |   | || | | (_| | (_|  __/  [/bold cyan]
[bold cyan] \\___/|_| |_| |_|_| |_|_|   |_||_|  \\__,_|\\___\\___|  [/bold cyan]
[dim]LangGraph Autonomous SRE Incident Triage Engine[/dim]
"""

def run_incident_triage(query: str):
    graph = build_incident_graph(enable_hitl=True)
    thread_id = str(uuid.uuid4())[:8]
    config = {"configurable": {"thread_id": thread_id}}

    initial_state = {
        "incident_query": query,
        "retry_count": 0,
        "messages": []
    }

    console.print(f"\n[cyan]Starting LangGraph execution (Thread: {thread_id})...[/cyan]")

    # Run up to human approval gate or completion
    with console.status("[bold green]Executing StateGraph nodes (Router -> Retriever/SQL -> Synthesis -> Critic)...[/bold green]"):
        graph.invoke(initial_state, config=config)

    state = graph.get_state(config)

    # Check if paused at human-in-the-loop gate
    if state.next == ("human_approval_gate",):
        remediation = state.values.get("proposed_remediation", "")
        service = state.values.get("service_name", "target service")

        console.print(Panel(
            f"[bold yellow]Action Required:[/bold yellow] Remediation for [green]{service}[/green] is marked sensitive:\n\n"
            f"[bold red]{remediation}[/bold red]",
            title="[bold yellow]Human-in-the-Loop Approval Gate[/bold yellow]",
            border_style="yellow"
        ))

        approval = Prompt.ask("[bold cyan]Approve remediation execution? [y/N][/bold cyan]", default="n")
        if approval.strip().lower() in ("y", "yes"):
            with console.status("[bold green]Resuming graph execution with human approval...[/bold green]"):
                res = graph.invoke(None, config=config)
            console.print(Panel(res.get("final_report", ""), title="[bold green]Final SRE Report[/bold green]", border_style="green"))
        else:
            console.print("[red]Remediation rejected by operator. Aborted execution.[/red]\n")
    else:
        report = state.values.get("final_report", "")
        console.print(Panel(report, title="[bold green]Final SRE Report[/bold green]", border_style="green"))

def main():
    console.clear()
    console.print(BANNER)
    console.print("[dim]Simulated SRE Incidents:")
    console.print("  1. 504 Gateway Timeout in checkout-service during payment processing")
    console.print("  2. Auth service Redis connection pool exhausted (500 Internal Server Error)")
    console.print("  3. Payment gateway P99 latency exceeding 4000ms with connection resets[/dim]\n")

    while True:
        try:
            query = Prompt.ask("[bold cyan]OmniTrace >[/bold cyan]")
            if not query or not query.strip():
                continue
            if query.strip().lower() in ("exit", "quit", "q"):
                console.print("[green]Exited.[/green]")
                break

            run_incident_triage(query)

        except KeyboardInterrupt:
            console.print("\n[yellow]Interrupted.[/yellow]")
            break
        except Exception as e:
            console.print(f"[bold red]Runtime Error:[/bold red] {e}\n")

if __name__ == "__main__":
    main()
