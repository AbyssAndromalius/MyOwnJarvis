#!/usr/bin/env python3
"""
Admin CLI for reviewing learning corrections.
Interacts with Learning Sidecar HTTP API.
"""
import argparse
import sys
import httpx
from datetime import datetime
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

SIDECAR_URL = "http://localhost:10003"
console = Console()


def format_datetime(iso_string: str) -> str:
    """Format ISO datetime for display."""
    try:
        dt = datetime.fromisoformat(iso_string.replace('Z', '+00:00'))
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    except:
        return iso_string


def list_pending():
    """List all pending corrections."""
    try:
        response = httpx.get(f"{SIDECAR_URL}/learning/pending", timeout=10.0)
        response.raise_for_status()
        data = response.json()
        
        if data['count'] == 0:
            console.print("[green]No corrections pending review.[/green]")
            return
        
        table = Table(title=f"Pending Corrections ({data['count']})")
        table.add_column("ID", style="cyan")
        table.add_column("User", style="magenta")
        table.add_column("Content", style="white")
        table.add_column("Submitted", style="yellow")
        
        for item in data['items']:
            table.add_row(
                item['id'][:8] + "...",
                item['user_id'],
                item['content'][:60] + "..." if len(item['content']) > 60 else item['content'],
                format_datetime(item['submitted_at'])
            )
        
        console.print(table)
        console.print(f"\n[dim]Use 'show <id>' to see details, 'approve <id>' or 'reject <id>' to review[/dim]")
        
    except httpx.HTTPError as e:
        console.print(f"[red]Error connecting to Learning Sidecar: {e}[/red]")
        sys.exit(1)
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        sys.exit(1)


def show_correction(correction_id: str):
    """Show detailed information about a correction."""
    try:
        response = httpx.get(f"{SIDECAR_URL}/learning/status/{correction_id}", timeout=10.0)
        response.raise_for_status()
        correction = response.json()
        
        # Basic info
        console.print(Panel(
            f"[bold]ID:[/bold] {correction['id']}\n"
            f"[bold]User:[/bold] {correction['user_id']}\n"
            f"[bold]Status:[/bold] {correction['final_status']}\n"
            f"[bold]Submitted:[/bold] {format_datetime(correction['submitted_at'])}\n"
            f"[bold]Personal Info:[/bold] {correction['personal_info']}\n\n"
            f"[bold]Content:[/bold]\n{correction['content']}",
            title="Correction Details"
        ))
        
        # Gate 1
        if correction['gate1']:
            gate1 = correction['gate1']
            console.print(Panel(
                f"[bold]Status:[/bold] {gate1['status']}\n"
                f"[bold]Reason:[/bold] {gate1['reason']}\n"
                f"[bold]Processed:[/bold] {format_datetime(gate1['processed_at'])}",
                title="Gate 1 - Sanity Check"
            ))
        
        # Gate 2a
        if correction['gate2a']:
            gate2a = correction['gate2a']
            console.print(Panel(
                f"[bold]Status:[/bold] {gate2a['status']}\n"
                f"[bold]Confidence:[/bold] {gate2a['confidence']:.2f}\n"
                f"[bold]Reason:[/bold] {gate2a['reason']}\n"
                f"[bold]Processed:[/bold] {format_datetime(gate2a['processed_at'])}",
                title="Gate 2a - Local Fact-Check"
            ))
        
        # Gate 2b
        if correction['gate2b']:
            gate2b = correction['gate2b']
            console.print(Panel(
                f"[bold]Status:[/bold] {gate2b['status']}\n"
                f"[bold]Reason:[/bold] {gate2b['reason']}\n"
                f"[bold]Processed:[/bold] {format_datetime(gate2b['processed_at'])}",
                title="Gate 2b - Claude Fact-Check"
            ))
        
        # Gate 3
        if correction['gate3']:
            gate3 = correction['gate3']
            gate3_info = (
                f"[bold]Status:[/bold] {gate3['status']}\n"
                f"[bold]Submitted:[/bold] {format_datetime(gate3['submitted_at'])}"
            )
            if gate3['reviewed_at']:
                gate3_info += f"\n[bold]Reviewed:[/bold] {format_datetime(gate3['reviewed_at'])}"
            if gate3['reviewer']:
                gate3_info += f"\n[bold]Reviewer:[/bold] {gate3['reviewer']}"
            if gate3['reject_reason']:
                gate3_info += f"\n[bold]Reject Reason:[/bold] {gate3['reject_reason']}"
            
            console.print(Panel(gate3_info, title="Gate 3 - Admin Review"))
        
        # Memory application
        if correction['applied_at']:
            console.print(Panel(
                f"[bold]Applied:[/bold] {format_datetime(correction['applied_at'])}\n"
                f"[bold]Memory ID:[/bold] {correction.get('memory_id', 'N/A')}",
                title="Memory Application"
            ))
        
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:
            console.print(f"[red]Correction not found: {correction_id}[/red]")
        else:
            console.print(f"[red]Error: {e}[/red]")
        sys.exit(1)
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        sys.exit(1)


def approve_correction(correction_id: str):
    """Approve a correction."""
    try:
        payload = {
            "action": "approve",
            "caller_id": "dad"
        }
        
        response = httpx.post(
            f"{SIDECAR_URL}/learning/review/{correction_id}",
            json=payload,
            timeout=30.0
        )
        response.raise_for_status()
        result = response.json()
        
        console.print(f"[green]✓ Correction approved and applied to memory[/green]")
        console.print(f"[dim]Memory ID: {result.get('memory_id', 'N/A')}[/dim]")
        
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:
            console.print(f"[red]Correction not found: {correction_id}[/red]")
        elif e.response.status_code == 400:
            error_data = e.response.json()
            console.print(f"[red]Error: {error_data.get('detail', 'Bad request')}[/red]")
        else:
            console.print(f"[red]Error: {e}[/red]")
        sys.exit(1)
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        sys.exit(1)


def reject_correction(correction_id: str, reason: str):
    """Reject a correction."""
    if not reason:
        console.print("[red]Error: --reason required for rejection[/red]")
        sys.exit(1)
    
    try:
        payload = {
            "action": "reject",
            "caller_id": "dad",
            "reason": reason
        }
        
        response = httpx.post(
            f"{SIDECAR_URL}/learning/review/{correction_id}",
            json=payload,
            timeout=30.0
        )
        response.raise_for_status()
        
        console.print(f"[yellow]✗ Correction rejected[/yellow]")
        console.print(f"[dim]Reason: {reason}[/dim]")
        
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:
            console.print(f"[red]Correction not found: {correction_id}[/red]")
        elif e.response.status_code == 400:
            error_data = e.response.json()
            console.print(f"[red]Error: {error_data.get('detail', 'Bad request')}[/red]")
        else:
            console.print(f"[red]Error: {e}[/red]")
        sys.exit(1)
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        sys.exit(1)


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(description="Review learning corrections")
    subparsers = parser.add_subparsers(dest='command', help='Commands')
    
    # list command
    subparsers.add_parser('list', help='List pending corrections')
    
    # show command
    show_parser = subparsers.add_parser('show', help='Show correction details')
    show_parser.add_argument('id', help='Correction ID')
    
    # approve command
    approve_parser = subparsers.add_parser('approve', help='Approve a correction')
    approve_parser.add_argument('id', help='Correction ID')
    
    # reject command
    reject_parser = subparsers.add_parser('reject', help='Reject a correction')
    reject_parser.add_argument('id', help='Correction ID')
    reject_parser.add_argument('--reason', required=True, help='Rejection reason')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        sys.exit(1)
    
    if args.command == 'list':
        list_pending()
    elif args.command == 'show':
        show_correction(args.id)
    elif args.command == 'approve':
        approve_correction(args.id)
    elif args.command == 'reject':
        reject_correction(args.id, args.reason)


if __name__ == '__main__':
    main()
