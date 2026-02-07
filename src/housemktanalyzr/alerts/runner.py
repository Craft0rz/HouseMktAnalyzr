"""CLI runner for scheduled alert checks.

Run via: python -m housemktanalyzr.alerts.runner
Or schedule with cron/Task Scheduler.
"""

import argparse
import asyncio
import logging
import sys

from rich.console import Console
from rich.logging import RichHandler

from .checker import AlertChecker
from .criteria import CriteriaManager
from .notifier import AlertNotifier

console = Console()


def setup_logging(verbose: bool = False) -> None:
    """Configure logging with Rich handler."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(message)s",
        handlers=[RichHandler(console=console, rich_tracebacks=True)],
    )


async def run_alert_check(
    only_new: bool = True,
    send_email: bool = True,
    verbose: bool = False,
) -> int:
    """Run all enabled alert checks and send notifications.

    Args:
        only_new: Only report new listings (not previously seen)
        send_email: Send email notifications if configured
        verbose: Enable verbose logging

    Returns:
        Total number of matches found
    """
    logger = logging.getLogger(__name__)
    checker = AlertChecker()
    notifier = AlertNotifier()

    criteria_mgr = CriteriaManager()
    enabled = criteria_mgr.get_enabled()

    if not enabled:
        console.print("[yellow]No enabled alert criteria found.[/yellow]")
        console.print("Create alerts in the dashboard or manually add criteria.")
        return 0

    console.print(f"[bold]Checking {len(enabled)} enabled alerts...[/bold]")
    console.print()

    total_matches = 0

    try:
        results = await checker.check_all(only_new=only_new)

        for criteria_id, matches in results.items():
            criteria = criteria_mgr.load(criteria_id)
            if not criteria:
                continue

            total_matches += len(matches)

            # Console notification
            notifier.notify_console(criteria, matches)

            # Email notification
            if send_email and matches and criteria.notify_email:
                if notifier.notify_email(criteria, matches):
                    console.print(f"[dim]Email sent to {criteria.notify_email}[/dim]")

    except Exception as e:
        logger.error(f"Error during alert check: {e}")
        if verbose:
            raise
        return -1

    console.print()
    console.print(f"[bold]Check complete. Total matches: {total_matches}[/bold]")

    return total_matches


def main() -> None:
    """Main entry point for CLI."""
    parser = argparse.ArgumentParser(
        description="HouseMktAnalyzr Alert Runner",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m housemktanalyzr.alerts.runner
  python -m housemktanalyzr.alerts.runner --all
  python -m housemktanalyzr.alerts.runner --no-email -v

Schedule with cron (check every hour):
  0 * * * * cd /path/to/project && python -m housemktanalyzr.alerts.runner
        """,
    )

    parser.add_argument(
        "--all",
        action="store_true",
        help="Show all matches, not just new listings",
    )
    parser.add_argument(
        "--no-email",
        action="store_true",
        help="Skip email notifications",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose logging",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List all saved criteria and exit",
    )

    args = parser.parse_args()

    setup_logging(verbose=args.verbose)

    # List mode
    if args.list:
        criteria_mgr = CriteriaManager()
        criteria_list = criteria_mgr.list_all()

        if not criteria_list:
            console.print("[yellow]No saved criteria found.[/yellow]")
            return

        console.print("[bold]Saved Alert Criteria:[/bold]")
        for c in criteria_list:
            status = "🟢" if c.enabled else "⚪"
            regions = ", ".join(c.regions)
            console.print(f"  {status} {c.name}")
            console.print(f"     ID: {c.id}")
            console.print(f"     Regions: {regions}")
            console.print(f"     Min Score: {c.min_score or 'Any'}")
            if c.last_checked:
                console.print(f"     Last Checked: {c.last_checked}")
            console.print()
        return

    # Run check
    try:
        result = asyncio.run(run_alert_check(
            only_new=not args.all,
            send_email=not args.no_email,
            verbose=args.verbose,
        ))
        sys.exit(0 if result >= 0 else 1)
    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted[/yellow]")
        sys.exit(130)


if __name__ == "__main__":
    main()
