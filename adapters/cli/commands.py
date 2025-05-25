"""CLI commands implementation using Typer."""

import asyncio
import json
import logging
from datetime import datetime
from typing import Optional, List
from uuid import UUID

import typer
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich import print as rprint

from config.settings import get_config
from adapters.config import ConfigAdapter
from adapters.db.database import initialize_database, migrate_database_sync
from adapters.db.repositories import (
    SQLUserRepository, SQLAccountRepository, 
    SQLEmailRepository, SQLTransmissionRecordRepository
)
from adapters.graph_api import GraphAPIAdapter
from adapters.external_api import ExternalAPIAdapter

from core.usecases.account_management import AccountManagementUseCase
from core.usecases.email_detection import EmailDetectionUseCase
from core.usecases.external_transmission import ExternalTransmissionUseCase
from core.usecases.multi_account_manager import (
    MultiAccountManagerUseCase,
    MultiAccountSyncRequest,
    TokenRefreshRequest,
    AccountHealthCheckRequest
)


# Initialize console for rich output
console = Console()

# Create main CLI app
app = typer.Typer(
    name="graphapi-query",
    help="Microsoft Graph API Email Query and Transmission System",
    add_completion=False
)

# Create sub-commands
account_app = typer.Typer(name="account", help="Account management commands")
email_app = typer.Typer(name="email", help="Email detection and management commands")
transmission_app = typer.Typer(name="transmission", help="External transmission commands")
db_app = typer.Typer(name="db", help="Database management commands")
config_app = typer.Typer(name="config", help="Configuration management commands")
multi_app = typer.Typer(name="multi", help="Multi-account management commands")

# Add sub-commands to main app
app.add_typer(account_app, name="account")
app.add_typer(email_app, name="email")
app.add_typer(transmission_app, name="transmission")
app.add_typer(db_app, name="db")
app.add_typer(config_app, name="config")
app.add_typer(multi_app, name="multi")


# Global dependencies
def get_dependencies():
    """Get initialized dependencies for CLI commands."""
    config = ConfigAdapter(get_config())
    db_adapter = initialize_database(config)
    
    # Get sync session for CLI operations
    session = db_adapter.get_session()
    
    # Initialize repositories
    user_repo = SQLUserRepository(session)
    account_repo = SQLAccountRepository(session)
    email_repo = SQLEmailRepository(session)
    transmission_repo = SQLTransmissionRecordRepository(session)
    
    # Initialize adapters
    graph_api = GraphAPIAdapter(config)
    external_api = ExternalAPIAdapter(config)
    
    # Initialize use cases
    account_usecase = AccountManagementUseCase(
        user_repo=user_repo,
        account_repo=account_repo,
        graph_api=graph_api,
        config=config
    )
    
    email_usecase = EmailDetectionUseCase(
        account_repo=account_repo,
        email_repo=email_repo,
        graph_api=graph_api,
        config=config
    )
    
    transmission_usecase = ExternalTransmissionUseCase(
        email_repo=email_repo,
        transmission_repo=transmission_repo,
        external_api=external_api,
        config=config
    )
    
    return {
        'config': config,
        'db_adapter': db_adapter,
        'session': session,
        'user_repo': user_repo,
        'account_repo': account_repo,
        'email_repo': email_repo,
        'transmission_repo': transmission_repo,
        'account_usecase': account_usecase,
        'email_usecase': email_usecase,
        'transmission_usecase': transmission_usecase,
        'graph_api': graph_api,
        'external_api': external_api
    }


def create_multi_account_manager(deps):
    """Create MultiAccountManagerUseCase with dependencies."""
    return MultiAccountManagerUseCase(
        account_management=deps['account_usecase'],
        email_detection=deps['email_usecase'],
        external_transmission=deps['transmission_usecase'],
        account_repository=deps['account_repo'],
        email_repository=deps['email_repo'],
        user_repository=deps['user_repo'],
        graph_api=deps['graph_api'],
        config=deps['config']
    )


# Multi-account management commands
@multi_app.command("sync-all")
def sync_all():
    """Sync all active accounts."""
    try:
        deps = get_dependencies()
        multi_account_manager = create_multi_account_manager(deps)
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console
        ) as progress:
            task = progress.add_task("Syncing all accounts...", total=None)
            
            result = asyncio.run(multi_account_manager.sync_all_accounts(
                MultiAccountSyncRequest(sync_active_only=True)
            ))
        
        console.print(f"[green]✅ Synced {result.successful_syncs}/{result.total_accounts} accounts[/green]")
        console.print(f"📧 Detected {result.total_emails_detected} emails")
        console.print(f"📤 Transmitted {result.total_emails_transmitted} emails")
        console.print(f"⏱️ Total duration: {result.total_duration_ms}ms")
        
        if result.account_results:
            # Show detailed results table
            table = Table(title="Account Sync Results")
            table.add_column("Email", style="cyan")
            table.add_column("Status", style="green")
            table.add_column("Emails", style="yellow")
            table.add_column("Transmitted", style="blue")
            table.add_column("Duration", style="magenta")
            
            for account_result in result.account_results:
                status_color = "green" if account_result.status == "success" else "red"
                table.add_row(
                    account_result.email,
                    f"[{status_color}]{account_result.status}[/{status_color}]",
                    str(account_result.emails_detected),
                    str(account_result.emails_transmitted),
                    f"{account_result.sync_duration_ms}ms"
                )
            
            console.print(table)
        
    except Exception as e:
        console.print(f"[red]Error syncing accounts: {e}[/red]")
        raise typer.Exit(1)


@multi_app.command("refresh-tokens")
def refresh_tokens(
    hours_before_expiry: int = typer.Option(24, "--hours", "-h", help="Refresh tokens expiring within this many hours")
):
    """Refresh expiring tokens."""
    try:
        deps = get_dependencies()
        multi_account_manager = create_multi_account_manager(deps)
        
        with console.status("[bold green]Refreshing tokens..."):
            result = asyncio.run(multi_account_manager.refresh_expiring_tokens(
                TokenRefreshRequest(hours_before_expiry=hours_before_expiry)
            ))
        
        console.print(f"[green]🔐 Refreshed {result.tokens_refreshed} tokens[/green]")
        console.print(f"❌ Failed {result.tokens_failed} tokens")
        console.print(f"📊 Checked {result.accounts_checked} accounts")
        
        if result.refresh_results:
            # Show refresh results table
            table = Table(title="Token Refresh Results")
            table.add_column("Email", style="cyan")
            table.add_column("Status", style="green")
            table.add_column("Error", style="red")
            
            for refresh_result in result.refresh_results:
                status_color = "green" if refresh_result["status"] == "refreshed" else "red"
                table.add_row(
                    refresh_result["email"],
                    f"[{status_color}]{refresh_result['status']}[/{status_color}]",
                    refresh_result.get("error", "")
                )
            
            console.print(table)
        
    except Exception as e:
        console.print(f"[red]Error refreshing tokens: {e}[/red]")
        raise typer.Exit(1)


@multi_app.command("health-check")
def health_check():
    """Check health of all accounts."""
    try:
        deps = get_dependencies()
        multi_account_manager = create_multi_account_manager(deps)
        
        with console.status("[bold green]Checking account health..."):
            result = asyncio.run(multi_account_manager.check_accounts_health(
                AccountHealthCheckRequest()
            ))
        
        console.print(f"[green]✅ Healthy accounts: {result.healthy_accounts}[/green]")
        console.print(f"[red]❌ Unhealthy accounts: {result.unhealthy_accounts}[/red]")
        console.print(f"📊 Total accounts: {result.total_accounts}")
        
        # Create health status table
        table = Table(title="Account Health Status")
        table.add_column("Email", style="cyan")
        table.add_column("Status", style="green")
        table.add_column("Token Valid", style="yellow")
        table.add_column("Last Sync", style="blue")
        table.add_column("Issues", style="red")
        
        for status in result.account_statuses:
            health_status = "✅ Healthy" if status.is_healthy else "❌ Unhealthy"
            token_status = "✓" if status.token_valid else "✗"
            last_sync = status.last_sync_at.strftime("%Y-%m-%d %H:%M") if status.last_sync_at else "Never"
            issues = ", ".join(status.issues) if status.issues else "None"
            
            table.add_row(
                status.email,
                health_status,
                token_status,
                last_sync,
                issues
            )
        
        console.print(table)
        
    except Exception as e:
        console.print(f"[red]Error checking account health: {e}[/red]")
        raise typer.Exit(1)


@multi_app.command("periodic-sync")
def periodic_sync(
    interval_minutes: int = typer.Option(5, "--interval", "-i", help="Sync interval in minutes"),
    max_duration_minutes: int = typer.Option(60, "--max-duration", "-d", help="Maximum duration in minutes")
):
    """Run periodic synchronization."""
    try:
        deps = get_dependencies()
        multi_account_manager = create_multi_account_manager(deps)
        
        console.print(f"[blue]🔄 Starting periodic sync (interval: {interval_minutes}min, max duration: {max_duration_minutes}min)[/blue]")
        
        result = asyncio.run(multi_account_manager.schedule_periodic_sync(
            interval_minutes=interval_minutes,
            max_duration_minutes=max_duration_minutes
        ))
        
        console.print(f"[green]✅ Periodic sync completed![/green]")
        console.print(f"🔄 Sync cycles: {result['sync_count']}")
        console.print(f"📧 Total emails detected: {result['total_emails_detected']}")
        console.print(f"⏱️ Duration: {result['duration_minutes']} minutes")
        
    except Exception as e:
        console.print(f"[red]Error running periodic sync: {e}[/red]")
        raise typer.Exit(1)


# Account management commands
@account_app.command("list")
def list_accounts(
    user_id: Optional[str] = typer.Option(None, "--user-id", "-u", help="Filter by user ID"),
    active_only: bool = typer.Option(False, "--active-only", "-a", help="Show only active accounts")
):
    """List all accounts or accounts for a specific user."""
    try:
        deps = get_dependencies()
        account_usecase = deps['account_usecase']
        
        with console.status("[bold green]Fetching accounts..."):
            if user_id:
                result = asyncio.run(account_usecase.get_user_accounts(UUID(user_id)))
                accounts = result.accounts
            elif active_only:
                result = asyncio.run(account_usecase.get_active_accounts())
                accounts = result.accounts
            else:
                # Get all accounts (this would need to be implemented)
                accounts = []
        
        if not accounts:
            console.print("[yellow]No accounts found.[/yellow]")
            return
        
        # Create table
        table = Table(title="Accounts")
        table.add_column("ID", style="cyan")
        table.add_column("Email", style="green")
        table.add_column("Display Name", style="blue")
        table.add_column("Status", style="magenta")
        table.add_column("Last Sync", style="yellow")
        
        for account in accounts:
            status = "🟢 Active" if account.is_active and account.is_authorized else "🔴 Inactive"
            last_sync = account.last_sync_at.strftime("%Y-%m-%d %H:%M") if account.last_sync_at else "Never"
            
            table.add_row(
                str(account.id)[:8] + "...",
                account.email,
                account.display_name or "N/A",
                status,
                last_sync
            )
        
        console.print(table)
        
    except Exception as e:
        console.print(f"[red]Error listing accounts: {e}[/red]")
        raise typer.Exit(1)


@account_app.command("add")
def add_account(
    username: str = typer.Option(..., "--username", "-u", help="Username for the account"),
    email: str = typer.Option(..., "--email", "-e", help="Email address"),
    display_name: Optional[str] = typer.Option(None, "--display-name", "-d", help="Display name")
):
    """Add a new account."""
    try:
        deps = get_dependencies()
        account_usecase = deps['account_usecase']
        
        with console.status("[bold green]Adding account..."):
            result = asyncio.run(account_usecase.create_account(
                username=username,
                email=email,
                display_name=display_name
            ))
        
        if result.success:
            console.print(f"[green]✓ Account added successfully![/green]")
            console.print(f"Account ID: {result.account.id}")
            console.print(f"Email: {result.account.email}")
        else:
            console.print(f"[red]✗ Failed to add account: {result.error}[/red]")
            raise typer.Exit(1)
            
    except Exception as e:
        console.print(f"[red]Error adding account: {e}[/red]")
        raise typer.Exit(1)


@account_app.command("authorize")
def authorize_account(
    account_id: str = typer.Argument(..., help="Account ID to authorize"),
    authorization_code: Optional[str] = typer.Option(None, "--code", "-c", help="Authorization code from OAuth flow")
):
    """Authorize an account with Microsoft Graph API."""
    try:
        deps = get_dependencies()
        account_usecase = deps['account_usecase']
        
        if not authorization_code:
            # Get authorization URL
            with console.status("[bold blue]Getting authorization URL..."):
                auth_result = asyncio.run(account_usecase.get_authorization_url(UUID(account_id)))
            
            if auth_result.success:
                console.print(Panel(
                    f"Please visit this URL to authorize the account:\n\n{auth_result.authorization_url}",
                    title="Authorization Required",
                    border_style="blue"
                ))
                authorization_code = typer.prompt("Enter the authorization code")
            else:
                console.print(f"[red]✗ Failed to get authorization URL: {auth_result.error}[/red]")
                raise typer.Exit(1)
        
        # Exchange code for token
        with console.status("[bold green]Exchanging authorization code..."):
            result = asyncio.run(account_usecase.authorize_account(
                UUID(account_id), 
                authorization_code
            ))
        
        if result.success:
            console.print(f"[green]✓ Account authorized successfully![/green]")
            console.print(f"Account: {result.account.email}")
            console.print(f"Status: {'Authorized' if result.account.is_authorized else 'Not Authorized'}")
        else:
            console.print(f"[red]✗ Authorization failed: {result.error}[/red]")
            raise typer.Exit(1)
            
    except Exception as e:
        console.print(f"[red]Error authorizing account: {e}[/red]")
        raise typer.Exit(1)


@account_app.command("remove")
def remove_account(
    account_id: str = typer.Argument(..., help="Account ID to remove"),
    force: bool = typer.Option(False, "--force", "-f", help="Force removal without confirmation")
):
    """Remove an account."""
    try:
        deps = get_dependencies()
        account_usecase = deps['account_usecase']
        
        if not force:
            confirm = typer.confirm(f"Are you sure you want to remove account {account_id}?")
            if not confirm:
                console.print("[yellow]Operation cancelled.[/yellow]")
                return
        
        with console.status("[bold red]Removing account..."):
            result = asyncio.run(account_usecase.remove_account(UUID(account_id)))
        
        if result.success:
            console.print(f"[green]✓ Account removed successfully![/green]")
        else:
            console.print(f"[red]✗ Failed to remove account: {result.error}[/red]")
            raise typer.Exit(1)
            
    except Exception as e:
        console.print(f"[red]Error removing account: {e}[/red]")
        raise typer.Exit(1)


# Email management commands
@email_app.command("detect")
def detect_emails(
    account_id: Optional[str] = typer.Option(None, "--account-id", "-a", help="Specific account ID"),
    limit: int = typer.Option(100, "--limit", "-l", help="Maximum number of emails to detect"),
    use_delta: bool = typer.Option(True, "--use-delta/--no-delta", help="Use delta query for incremental sync")
):
    """Detect new emails from Microsoft Graph API."""
    try:
        deps = get_dependencies()
        email_usecase = deps['email_usecase']
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console
        ) as progress:
            task = progress.add_task("Detecting emails...", total=None)
            
            if account_id:
                result = asyncio.run(email_usecase.detect_emails_for_account(
                    UUID(account_id), 
                    limit=limit,
                    use_delta=use_delta
                ))
            else:
                result = asyncio.run(email_usecase.detect_emails_for_all_accounts(
                    limit=limit,
                    use_delta=use_delta
                ))
        
        if result.success:
            console.print(f"[green]✓ Email detection completed![/green]")
            console.print(f"Emails detected: {len(result.emails)}")
            console.print(f"New emails: {result.new_count}")
            console.print(f"Updated emails: {result.updated_count}")
            
            if result.emails:
                # Show summary table
                table = Table(title="Detected Emails")
                table.add_column("Subject", style="cyan", max_width=50)
                table.add_column("Sender", style="green")
                table.add_column("Received", style="yellow")
                table.add_column("Status", style="magenta")
                
                for email in result.emails[:10]:  # Show first 10
                    received = email.received_at.strftime("%m-%d %H:%M") if email.received_at else "N/A"
                    table.add_row(
                        email.subject[:47] + "..." if len(email.subject) > 50 else email.subject,
                        email.sender,
                        received,
                        email.processing_status
                    )
                
                console.print(table)
                
                if len(result.emails) > 10:
                    console.print(f"[dim]... and {len(result.emails) - 10} more emails[/dim]")
        else:
            console.print(f"[red]✗ Email detection failed: {result.error}[/red]")
            raise typer.Exit(1)
            
    except Exception as e:
        console.print(f"[red]Error detecting emails: {e}[/red]")
        raise typer.Exit(1)


@email_app.command("list")
def list_emails(
    account_id: Optional[str] = typer.Option(None, "--account-id", "-a", help="Filter by account ID"),
    status: Optional[str] = typer.Option(None, "--status", "-s", help="Filter by processing status"),
    limit: int = typer.Option(20, "--limit", "-l", help="Maximum number of emails to show")
):
    """List emails in the database."""
    try:
        deps = get_dependencies()
        email_usecase = deps['email_usecase']
        
        with console.status("[bold green]Fetching emails..."):
            if account_id:
                result = asyncio.run(email_usecase.get_emails_by_account(
                    UUID(account_id), 
                    limit=limit
                ))
                emails = result.emails
            elif status:
                result = asyncio.run(email_usecase.get_emails_by_status(
                    status, 
                    limit=limit
                ))
                emails = result.emails
            else:
                # Get recent emails (this would need to be implemented)
                emails = []
        
        if not emails:
            console.print("[yellow]No emails found.[/yellow]")
            return
        
        # Create table
        table = Table(title=f"Emails ({len(emails)} found)")
        table.add_column("ID", style="cyan")
        table.add_column("Subject", style="green", max_width=40)
        table.add_column("Sender", style="blue", max_width=30)
        table.add_column("Received", style="yellow")
        table.add_column("Status", style="magenta")
        
        for email in emails:
            received = email.received_at.strftime("%m-%d %H:%M") if email.received_at else "N/A"
            subject = email.subject[:37] + "..." if len(email.subject) > 40 else email.subject
            
            table.add_row(
                str(email.id)[:8] + "...",
                subject,
                email.sender[:27] + "..." if len(email.sender) > 30 else email.sender,
                received,
                email.processing_status
            )
        
        console.print(table)
        
    except Exception as e:
        console.print(f"[red]Error listing emails: {e}[/red]")
        raise typer.Exit(1)


# Transmission commands
@transmission_app.command("send")
def send_emails(
    status: str = typer.Option("pending", "--status", "-s", help="Email status to send"),
    limit: int = typer.Option(50, "--limit", "-l", help="Maximum number of emails to send"),
    endpoint: Optional[str] = typer.Option(None, "--endpoint", "-e", help="Specific API endpoint")
):
    """Send emails to external API."""
    try:
        deps = get_dependencies()
        transmission_usecase = deps['transmission_usecase']
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console
        ) as progress:
            task = progress.add_task("Sending emails...", total=None)
            
            result = asyncio.run(transmission_usecase.transmit_pending_emails(
                limit=limit,
                endpoint=endpoint
            ))
        
        if result.success:
            console.print(f"[green]✓ Email transmission completed![/green]")
            console.print(f"Total processed: {result.total_processed}")
            console.print(f"Successful: {result.successful_count}")
            console.print(f"Failed: {result.failed_count}")
            
            if result.transmission_records:
                # Show summary table
                table = Table(title="Transmission Results")
                table.add_column("Email ID", style="cyan")
                table.add_column("Status", style="green")
                table.add_column("Response Code", style="yellow")
                table.add_column("Processing Time", style="magenta")
                
                for record in result.transmission_records[:10]:  # Show first 10
                    status_color = "green" if record.status == "success" else "red"
                    table.add_row(
                        str(record.email_id)[:8] + "...",
                        f"[{status_color}]{record.status}[/{status_color}]",
                        str(record.response_status_code) if record.response_status_code else "N/A",
                        f"{record.processing_time_ms}ms" if record.processing_time_ms else "N/A"
                    )
                
                console.print(table)
        else:
            console.print(f"[red]✗ Email transmission failed: {result.error}[/red]")
            raise typer.Exit(1)
            
    except Exception as e:
        console.print(f"[red]Error sending emails: {e}[/red]")
        raise typer.Exit(1)


@transmission_app.command("retry")
def retry_failed_transmissions(
    limit: int = typer.Option(20, "--limit", "-l", help="Maximum number of retries")
):
    """Retry failed transmissions."""
    try:
        deps = get_dependencies()
        transmission_usecase = deps['transmission_usecase']
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console
        ) as progress:
            task = progress.add_task("Retrying failed transmissions...", total=None)
            
            result = asyncio.run(transmission_usecase.retry_failed_transmissions(limit=limit))
        
        if result.success:
            console.print(f"[green]✓ Retry completed![/green]")
            console.print(f"Retried: {result.total_processed}")
            console.print(f"Successful: {result.successful_count}")
            console.print(f"Still failed: {result.failed_count}")
        else:
            console.print(f"[red]✗ Retry failed: {result.error}[/red]")
            raise typer.Exit(1)
            
    except Exception as e:
        console.print(f"[red]Error retrying transmissions: {e}[/red]")
        raise typer.Exit(1)


@transmission_app.command("status")
def transmission_status():
    """Show transmission status summary."""
    try:
        deps = get_dependencies()
        transmission_usecase = deps['transmission_usecase']
        
        with console.status("[bold green]Getting transmission status..."):
            result = asyncio.run(transmission_usecase.get_transmission_summary())
        
        if result.success:
            summary = result.summary
            
            # Create status panel
            status_text = f"""
[green]✓ Successful:[/green] {summary.get('successful', 0)}
[yellow]⏳ Pending:[/yellow] {summary.get('pending', 0)}
[blue]🔄 Processing:[/blue] {summary.get('processing', 0)}
[red]✗ Failed:[/red] {summary.get('failed', 0)}
[orange]🔁 Retry:[/orange] {summary.get('retry', 0)}

[bold]Total Records:[/bold] {summary.get('total', 0)}
            """
            
            console.print(Panel(
                status_text.strip(),
                title="Transmission Status",
                border_style="blue"
            ))
        else:
            console.print(f"[red]✗ Failed to get status: {result.error}[/red]")
            raise typer.Exit(1)
            
    except Exception as e:
        console.print(f"[red]Error getting transmission status: {e}[/red]")
        raise typer.Exit(1)


# Database management commands
@db_app.command("migrate")
def migrate_database(
    drop_existing: bool = typer.Option(False, "--drop-existing", help="Drop existing tables first")
):
    """Run database migrations."""
    try:
        config = ConfigAdapter(get_config())
        
        with console.status("[bold green]Running database migration..."):
            migrate_database_sync(config, drop_existing=drop_existing)
        
        console.print("[green]✓ Database migration completed successfully![/green]")
        
    except Exception as e:
        console.print(f"[red]Error running migration: {e}[/red]")
        raise typer.Exit(1)


@db_app.command("health")
def database_health():
    """Check database health."""
    try:
        deps = get_dependencies()
        db_adapter = deps['db_adapter']
        
        with console.status("[bold green]Checking database health..."):
            is_healthy = db_adapter.sync_health_check()
        
        if is_healthy:
            console.print("[green]✓ Database is healthy![/green]")
        else:
            console.print("[red]✗ Database health check failed![/red]")
            raise typer.Exit(1)
            
    except Exception as e:
        console.print(f"[red]Error checking database health: {e}[/red]")
        raise typer.Exit(1)


# Configuration commands
@config_app.command("show")
def show_config():
    """Show current configuration (with sensitive data masked)."""
    try:
        config = ConfigAdapter(get_config())
        
        config_info = {
            "Environment": config.get_environment(),
            "Database URL": config.get_database_url().split('@')[-1] if '@' in config.get_database_url() else config.get_database_url(),
            "Graph API Endpoint": config.get_graph_api_endpoint(),
            "External API URL": config.get_external_api_url(),
            "Client ID": config.get_client_id()[:8] + "..." if config.get_client_id() else "Not set",
            "Client Secret": "Set" if config.get_client_secret() else "Not set",
            "External API Key": "Set" if config.get_external_api_key() else "Not set"
        }
        
        # Create configuration table
        table = Table(title="Configuration")
        table.add_column("Setting", style="cyan")
        table.add_column("Value", style="green")
        
        for key, value in config_info.items():
            table.add_row(key, str(value))
        
        console.print(table)
        
    except Exception as e:
        console.print(f"[red]Error showing configuration: {e}[/red]")
        raise typer.Exit(1)


@config_app.command("test")
def test_connections():
    """Test connections to external services."""
    try:
        deps = get_dependencies()
        graph_api = deps['graph_api']
        external_api = deps['external_api']
        
        console.print("[bold blue]Testing connections...[/bold blue]")
        
        # Test Graph API
        with console.status("[bold green]Testing Graph API..."):
            graph_healthy = asyncio.run(graph_api.health_check())
        
        if graph_healthy:
            console.print("[green]✓ Graph API connection: OK[/green]")
        else:
            console.print("[red]✗ Graph API connection: FAILED[/red]")
        
        # Test External API
        with console.status("[bold green]Testing External API..."):
            external_healthy = asyncio.run(external_api.health_check())
        
        if external_healthy:
            console.print("[green]✓ External API connection: OK[/green]")
        else:
            console.print("[red]✗ External API connection: FAILED[/red]")
        
        # Overall status
        if graph_healthy and external_healthy:
            console.print("\n[green]✓ All connections are healthy![/green]")
        else:
            console.print("\n[red]✗ Some connections failed![/red]")
            raise typer.Exit(1)
            
    except Exception as e:
        console.print(f"[red]Error testing connections: {e}[/red]")
        raise typer.Exit(1)


# Main command
@app.command()
def version():
    """Show version information."""
    console.print("[bold blue]GraphAPI Query System[/bold blue]")
    console.print("Version: 1.0.0")
    console.print("Microsoft Graph API Email Detection and Transmission")


def create_cli_app():
    """Create and return the CLI application."""
    return app


if __name__ == "__main__":
    app()
