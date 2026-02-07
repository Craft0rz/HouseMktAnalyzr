"""Email notification sender for alerts using SMTP."""

import logging
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

logger = logging.getLogger(__name__)


def _get_smtp_config() -> dict:
    """Get SMTP config from environment variables."""
    host = os.environ.get("SMTP_HOST")
    if not host:
        raise RuntimeError("SMTP_HOST not configured")
    return {
        "host": host,
        "port": int(os.environ.get("SMTP_PORT", 587)),
        "user": os.environ.get("SMTP_USER", ""),
        "password": os.environ.get("SMTP_PASSWORD", ""),
        "from_email": os.environ.get("SMTP_FROM", os.environ.get("SMTP_USER", "")),
        "use_tls": os.environ.get("SMTP_TLS", "true").lower() in ("true", "1"),
    }


def _format_price(price: int) -> str:
    return f"${price:,}"


def _build_html(
    alert_name: str,
    new_listings: list,
    price_drops: list[dict],
) -> str:
    """Build HTML email body."""
    sections = []

    if new_listings:
        rows = ""
        for listing, metrics in new_listings[:20]:
            score_color = "#22c55e" if metrics.score >= 70 else "#eab308" if metrics.score >= 50 else "#ef4444"
            cf = metrics.cash_flow_monthly
            cf_str = f"{_format_price(int(cf))}/mo" if cf is not None else "-"
            cf_color = "#22c55e" if cf and cf > 0 else "#ef4444"
            cap = f"{metrics.cap_rate:.1f}%" if metrics.cap_rate else "-"

            rows += f"""
            <tr>
                <td style="padding:8px;border-bottom:1px solid #eee;">
                    <a href="{listing.url}" style="color:#2563eb;text-decoration:none;">{listing.address}</a>
                    <br><span style="color:#666;font-size:12px;">{listing.city}</span>
                </td>
                <td style="padding:8px;border-bottom:1px solid #eee;text-align:center;">
                    <span style="background:{score_color};color:#fff;padding:2px 8px;border-radius:12px;font-weight:bold;">{metrics.score:.0f}</span>
                </td>
                <td style="padding:8px;border-bottom:1px solid #eee;text-align:right;">{_format_price(listing.price)}</td>
                <td style="padding:8px;border-bottom:1px solid #eee;text-align:center;">{cap}</td>
                <td style="padding:8px;border-bottom:1px solid #eee;text-align:right;color:{cf_color};">{cf_str}</td>
            </tr>"""

        sections.append(f"""
        <h2 style="color:#1e293b;margin:24px 0 12px;">New Matches ({len(new_listings)})</h2>
        <table style="width:100%;border-collapse:collapse;font-size:14px;">
            <tr style="background:#f8fafc;">
                <th style="padding:8px;text-align:left;">Address</th>
                <th style="padding:8px;text-align:center;">Score</th>
                <th style="padding:8px;text-align:right;">Price</th>
                <th style="padding:8px;text-align:center;">Cap Rate</th>
                <th style="padding:8px;text-align:right;">Cash Flow</th>
            </tr>
            {rows}
        </table>
        """)

    if price_drops:
        rows = ""
        for drop in price_drops[:20]:
            rows += f"""
            <tr>
                <td style="padding:8px;border-bottom:1px solid #eee;">{drop['address']}</td>
                <td style="padding:8px;border-bottom:1px solid #eee;text-align:right;text-decoration:line-through;color:#999;">{_format_price(drop['old_price'])}</td>
                <td style="padding:8px;border-bottom:1px solid #eee;text-align:right;color:#22c55e;font-weight:bold;">{_format_price(drop['new_price'])}</td>
                <td style="padding:8px;border-bottom:1px solid #eee;text-align:right;color:#22c55e;">-{_format_price(drop['drop_amount'])} ({drop['drop_pct']}%)</td>
            </tr>"""

        sections.append(f"""
        <h2 style="color:#1e293b;margin:24px 0 12px;">Price Drops ({len(price_drops)})</h2>
        <table style="width:100%;border-collapse:collapse;font-size:14px;">
            <tr style="background:#f8fafc;">
                <th style="padding:8px;text-align:left;">Address</th>
                <th style="padding:8px;text-align:right;">Old Price</th>
                <th style="padding:8px;text-align:right;">New Price</th>
                <th style="padding:8px;text-align:right;">Drop</th>
            </tr>
            {rows}
        </table>
        """)

    body = "\n".join(sections)

    return f"""
    <div style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;max-width:700px;margin:0 auto;padding:20px;">
        <h1 style="color:#0f172a;font-size:20px;margin-bottom:4px;">Alert: {alert_name}</h1>
        <p style="color:#64748b;margin-top:0;">HouseMktAnalyzr found updates matching your criteria.</p>
        {body}
        <hr style="border:none;border-top:1px solid #e2e8f0;margin:24px 0;">
        <p style="color:#94a3b8;font-size:12px;">
            You're receiving this because you set up an alert on HouseMktAnalyzr.
        </p>
    </div>
    """


async def send_alert_email(
    to_email: str,
    alert_name: str,
    new_listings: list,
    price_drops: list[dict],
):
    """Send an alert notification email.

    Runs SMTP in a thread to avoid blocking the event loop.
    """
    import asyncio

    config = _get_smtp_config()

    html = _build_html(alert_name, new_listings, price_drops)

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"HouseMktAnalyzr Alert: {alert_name}"
    msg["From"] = config["from_email"]
    msg["To"] = to_email

    # Plain text fallback
    text_parts = [f"Alert: {alert_name}\n"]
    if new_listings:
        text_parts.append(f"\n{len(new_listings)} new matches found:")
        for listing, metrics in new_listings[:10]:
            text_parts.append(
                f"  - {listing.address} | {_format_price(listing.price)} | "
                f"Score: {metrics.score:.0f} | {listing.url}"
            )
    if price_drops:
        text_parts.append(f"\n{len(price_drops)} price drops:")
        for drop in price_drops[:10]:
            text_parts.append(
                f"  - {drop['address']} | {_format_price(drop['old_price'])} -> "
                f"{_format_price(drop['new_price'])} (-{drop['drop_pct']}%)"
            )

    msg.attach(MIMEText("\n".join(text_parts), "plain"))
    msg.attach(MIMEText(html, "html"))

    def _send():
        with smtplib.SMTP(config["host"], config["port"]) as server:
            if config["use_tls"]:
                server.starttls()
            if config["user"] and config["password"]:
                server.login(config["user"], config["password"])
            server.sendmail(config["from_email"], [to_email], msg.as_string())

    await asyncio.get_event_loop().run_in_executor(None, _send)
    logger.info(f"Alert email sent to {to_email} for '{alert_name}'")
