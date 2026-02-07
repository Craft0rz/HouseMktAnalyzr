"""Alert notification system."""

import logging
import os
import smtplib
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional

from rich.console import Console
from rich.table import Table

from ..models.property import InvestmentMetrics, PropertyListing
from .criteria import AlertCriteria

logger = logging.getLogger(__name__)
console = Console()


class AlertNotifier:
    """Send alert notifications for matching properties.

    Supports console output (Rich formatted) and email notifications.

    Example:
        notifier = AlertNotifier()
        notifier.notify_console(criteria, matches)

        # With email
        notifier.notify_email(criteria, matches)
    """

    def __init__(
        self,
        smtp_host: Optional[str] = None,
        smtp_port: Optional[int] = None,
        smtp_user: Optional[str] = None,
        smtp_password: Optional[str] = None,
    ):
        """Initialize notifier with optional SMTP settings.

        Settings can be provided directly or via environment variables:
        - SMTP_HOST
        - SMTP_PORT
        - SMTP_USER
        - SMTP_PASSWORD

        Args:
            smtp_host: SMTP server hostname
            smtp_port: SMTP server port
            smtp_user: SMTP username
            smtp_password: SMTP password
        """
        self.smtp_host = smtp_host or os.environ.get("SMTP_HOST")
        self.smtp_port = int(smtp_port or os.environ.get("SMTP_PORT", 587))
        self.smtp_user = smtp_user or os.environ.get("SMTP_USER")
        self.smtp_password = smtp_password or os.environ.get("SMTP_PASSWORD")

    def notify_console(
        self,
        criteria: AlertCriteria,
        matches: list[tuple[PropertyListing, InvestmentMetrics]],
    ) -> None:
        """Print matches to console with Rich formatting.

        Args:
            criteria: The alert criteria that matched
            matches: List of matching (PropertyListing, InvestmentMetrics)
        """
        if not matches:
            console.print(f"[dim]No new matches for: {criteria.name}[/dim]")
            return

        console.print()
        console.print(f"[bold green]🔔 Alert: {criteria.name}[/bold green]")
        console.print(f"[dim]Found {len(matches)} matching properties[/dim]")
        console.print()

        # Create table
        table = Table(show_header=True, header_style="bold")
        table.add_column("Score", justify="right")
        table.add_column("Address", max_width=35)
        table.add_column("City")
        table.add_column("Type")
        table.add_column("Price", justify="right")
        table.add_column("Cap Rate", justify="right")
        table.add_column("Cash Flow", justify="right")

        for listing, metrics in sorted(matches, key=lambda x: x[1].score, reverse=True):
            # Color score
            if metrics.score >= 70:
                score_str = f"[green]{metrics.score:.0f}[/green]"
            elif metrics.score >= 50:
                score_str = f"[yellow]{metrics.score:.0f}[/yellow]"
            else:
                score_str = f"[red]{metrics.score:.0f}[/red]"

            cap_rate = f"{metrics.cap_rate:.1f}%" if metrics.cap_rate else "N/A"
            cash_flow = f"${metrics.cash_flow_monthly:,.0f}" if metrics.cash_flow_monthly else "N/A"

            table.add_row(
                score_str,
                listing.address[:35],
                listing.city,
                listing.property_type.value,
                f"${listing.price:,}",
                cap_rate,
                cash_flow,
            )

        console.print(table)
        console.print()

    def generate_report(
        self,
        criteria: AlertCriteria,
        matches: list[tuple[PropertyListing, InvestmentMetrics]],
    ) -> str:
        """Generate text report of matches.

        Args:
            criteria: The alert criteria
            matches: Matching properties

        Returns:
            Formatted text report
        """
        lines = [
            f"Alert: {criteria.name}",
            f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            f"Found: {len(matches)} matching properties",
            "",
            "-" * 60,
            "",
        ]

        for listing, metrics in sorted(matches, key=lambda x: x[1].score, reverse=True):
            cap_rate = f"{metrics.cap_rate:.1f}%" if metrics.cap_rate else "N/A"
            cash_flow = f"${metrics.cash_flow_monthly:,.0f}/mo" if metrics.cash_flow_monthly else "N/A"

            lines.extend([
                f"📍 {listing.address}",
                f"   {listing.property_type.value} | {listing.city} | ${listing.price:,}",
                f"   Score: {metrics.score:.0f}/100 | Cap: {cap_rate} | Cash Flow: {cash_flow}",
                f"   {listing.url}",
                "",
            ])

        return "\n".join(lines)

    def generate_html_report(
        self,
        criteria: AlertCriteria,
        matches: list[tuple[PropertyListing, InvestmentMetrics]],
    ) -> str:
        """Generate HTML report for email.

        Args:
            criteria: The alert criteria
            matches: Matching properties

        Returns:
            HTML formatted report
        """
        rows = []
        for listing, metrics in sorted(matches, key=lambda x: x[1].score, reverse=True):
            cap_rate = f"{metrics.cap_rate:.1f}%" if metrics.cap_rate else "N/A"
            cash_flow = f"${metrics.cash_flow_monthly:,.0f}" if metrics.cash_flow_monthly else "N/A"

            # Score color
            if metrics.score >= 70:
                score_color = "#22c55e"
            elif metrics.score >= 50:
                score_color = "#eab308"
            else:
                score_color = "#ef4444"

            rows.append(f"""
            <tr>
                <td style="text-align:center;background-color:{score_color};color:white;font-weight:bold;">{metrics.score:.0f}</td>
                <td><a href="{listing.url}">{listing.address}</a></td>
                <td>{listing.city}</td>
                <td>{listing.property_type.value}</td>
                <td style="text-align:right;">${listing.price:,}</td>
                <td style="text-align:right;">{cap_rate}</td>
                <td style="text-align:right;">{cash_flow}</td>
            </tr>
            """)

        return f"""
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; }}
                table {{ border-collapse: collapse; width: 100%; }}
                th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
                th {{ background-color: #4a5568; color: white; }}
                tr:nth-child(even) {{ background-color: #f2f2f2; }}
                a {{ color: #3b82f6; text-decoration: none; }}
            </style>
        </head>
        <body>
            <h2>🏠 HouseMktAnalyzr Alert: {criteria.name}</h2>
            <p>Found <strong>{len(matches)}</strong> matching properties</p>

            <table>
                <tr>
                    <th>Score</th>
                    <th>Address</th>
                    <th>City</th>
                    <th>Type</th>
                    <th>Price</th>
                    <th>Cap Rate</th>
                    <th>Cash Flow</th>
                </tr>
                {"".join(rows)}
            </table>

            <p style="color:#888;margin-top:20px;">
                Generated by HouseMktAnalyzr on {datetime.now().strftime('%Y-%m-%d %H:%M')}
            </p>
        </body>
        </html>
        """

    def notify_email(
        self,
        criteria: AlertCriteria,
        matches: list[tuple[PropertyListing, InvestmentMetrics]],
    ) -> bool:
        """Send email notification.

        Args:
            criteria: The alert criteria
            matches: Matching properties

        Returns:
            True if email sent successfully
        """
        if not criteria.notify_email:
            logger.warning("No email configured for criteria")
            return False

        if not all([self.smtp_host, self.smtp_user, self.smtp_password]):
            logger.warning("SMTP not configured, skipping email")
            return False

        if not matches:
            logger.info("No matches, skipping email")
            return False

        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = f"🏠 HouseMktAnalyzr: {len(matches)} new matches for {criteria.name}"
            msg["From"] = self.smtp_user
            msg["To"] = criteria.notify_email

            # Plain text version
            text_part = MIMEText(self.generate_report(criteria, matches), "plain")
            msg.attach(text_part)

            # HTML version
            html_part = MIMEText(self.generate_html_report(criteria, matches), "html")
            msg.attach(html_part)

            # Send
            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                server.starttls()
                server.login(self.smtp_user, self.smtp_password)
                server.send_message(msg)

            logger.info(f"Email sent to {criteria.notify_email}")
            return True

        except Exception as e:
            logger.error(f"Failed to send email: {e}")
            return False
