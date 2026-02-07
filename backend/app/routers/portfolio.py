"""Portfolio management API endpoints backed by Postgres."""

import logging
import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from ..db import get_pool

router = APIRouter()
logger = logging.getLogger(__name__)


class PortfolioStatus(str, Enum):
    """Portfolio item status."""
    OWNED = "owned"
    WATCHING = "watching"


class PortfolioItemBase(BaseModel):
    """Base portfolio item fields."""
    property_id: str
    status: PortfolioStatus
    address: str
    property_type: str
    purchase_price: Optional[int] = None
    purchase_date: Optional[str] = None
    down_payment: Optional[int] = None
    mortgage_rate: Optional[float] = None
    current_rent: Optional[int] = None
    current_expenses: Optional[int] = None
    notes: Optional[str] = None


class CreatePortfolioItemRequest(PortfolioItemBase):
    """Request to add item to portfolio."""
    pass


class UpdatePortfolioItemRequest(BaseModel):
    """Request to update portfolio item."""
    status: Optional[PortfolioStatus] = None
    purchase_price: Optional[int] = None
    purchase_date: Optional[str] = None
    down_payment: Optional[int] = None
    mortgage_rate: Optional[float] = None
    current_rent: Optional[int] = None
    current_expenses: Optional[int] = None
    notes: Optional[str] = None


class PortfolioItemResponse(PortfolioItemBase):
    """Portfolio item response."""
    id: str
    created_at: str
    updated_at: str
    monthly_cash_flow: Optional[int] = None
    annual_return: Optional[float] = None
    equity: Optional[int] = None


class PortfolioListResponse(BaseModel):
    """Portfolio list response."""
    items: list[PortfolioItemResponse]
    count: int
    summary: dict


def _calculate_metrics(row) -> dict:
    """Calculate performance metrics for owned properties."""
    metrics = {"monthly_cash_flow": None, "annual_return": None, "equity": None}

    if row["status"] != "owned":
        return metrics

    purchase_price = row["purchase_price"]
    current_rent = row["current_rent"]
    current_expenses = row["current_expenses"] or 0
    down_payment = row["down_payment"]

    if purchase_price and current_rent:
        monthly_cf = current_rent - current_expenses
        metrics["monthly_cash_flow"] = monthly_cf

        if down_payment and down_payment > 0:
            annual_cf = monthly_cf * 12
            metrics["annual_return"] = round((annual_cf / down_payment) * 100, 2)
            metrics["equity"] = down_payment

    return metrics


def _row_to_response(row) -> PortfolioItemResponse:
    """Convert a database row to PortfolioItemResponse."""
    metrics = _calculate_metrics(row)
    return PortfolioItemResponse(
        id=row["id"],
        property_id=row["property_id"],
        status=PortfolioStatus(row["status"]),
        address=row["address"],
        property_type=row["property_type"],
        purchase_price=row["purchase_price"],
        purchase_date=row["purchase_date"],
        down_payment=row["down_payment"],
        mortgage_rate=row["mortgage_rate"],
        current_rent=row["current_rent"],
        current_expenses=row["current_expenses"],
        notes=row["notes"],
        created_at=row["created_at"].isoformat() if row["created_at"] else "",
        updated_at=row["updated_at"].isoformat() if row["updated_at"] else "",
        monthly_cash_flow=metrics["monthly_cash_flow"],
        annual_return=metrics["annual_return"],
        equity=metrics["equity"],
    )


def _calculate_summary(items: list[PortfolioItemResponse]) -> dict:
    """Calculate portfolio summary."""
    owned = [i for i in items if i.status == PortfolioStatus.OWNED]
    watching = [i for i in items if i.status == PortfolioStatus.WATCHING]

    total_invested = sum(i.purchase_price or 0 for i in owned)
    total_equity = sum(i.equity or 0 for i in owned)
    monthly_cf = sum(i.monthly_cash_flow or 0 for i in owned)

    returns = [i.annual_return for i in owned if i.annual_return is not None]
    avg_return = sum(returns) / len(returns) if returns else 0

    return {
        "total_owned": len(owned),
        "total_watching": len(watching),
        "total_invested": total_invested,
        "total_equity": total_equity,
        "monthly_cash_flow": monthly_cf,
        "annual_cash_flow": monthly_cf * 12,
        "avg_return": round(avg_return, 2),
    }


@router.get("", response_model=PortfolioListResponse)
async def list_portfolio(
    status: Optional[PortfolioStatus] = Query(default=None, description="Filter by status"),
) -> PortfolioListResponse:
    """List all portfolio items."""
    try:
        pool = get_pool()
        async with pool.acquire() as conn:
            if status:
                rows = await conn.fetch(
                    "SELECT * FROM portfolio WHERE status = $1 ORDER BY updated_at DESC",
                    status.value,
                )
            else:
                rows = await conn.fetch("SELECT * FROM portfolio ORDER BY updated_at DESC")

        items = [_row_to_response(row) for row in rows]
        return PortfolioListResponse(
            items=items, count=len(items), summary=_calculate_summary(items),
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list portfolio: {str(e)}")


@router.post("", response_model=PortfolioItemResponse, status_code=201)
async def add_to_portfolio(request: CreatePortfolioItemRequest) -> PortfolioItemResponse:
    """Add a property to portfolio."""
    try:
        pool = get_pool()
        item_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)

        async with pool.acquire() as conn:
            existing = await conn.fetchrow(
                "SELECT id FROM portfolio WHERE property_id = $1", request.property_id,
            )
            if existing:
                raise HTTPException(status_code=400, detail="Property already in portfolio")

            await conn.execute(
                """
                INSERT INTO portfolio (
                    id, property_id, status, address, property_type,
                    purchase_price, purchase_date, down_payment, mortgage_rate,
                    current_rent, current_expenses, notes,
                    created_at, updated_at
                ) VALUES (
                    $1, $2, $3, $4, $5,
                    $6, $7, $8, $9,
                    $10, $11, $12,
                    $13, $13
                )
                """,
                item_id, request.property_id, request.status.value,
                request.address, request.property_type,
                request.purchase_price, request.purchase_date,
                request.down_payment, request.mortgage_rate,
                request.current_rent, request.current_expenses,
                request.notes, now,
            )

            row = await conn.fetchrow("SELECT * FROM portfolio WHERE id = $1", item_id)

        return _row_to_response(row)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to add to portfolio: {str(e)}")


@router.get("/{item_id}", response_model=PortfolioItemResponse)
async def get_portfolio_item(item_id: str) -> PortfolioItemResponse:
    """Get a specific portfolio item."""
    try:
        pool = get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow("SELECT * FROM portfolio WHERE id = $1", item_id)

        if not row:
            raise HTTPException(status_code=404, detail="Portfolio item not found")

        return _row_to_response(row)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get portfolio item: {str(e)}")


@router.put("/{item_id}", response_model=PortfolioItemResponse)
async def update_portfolio_item(item_id: str, request: UpdatePortfolioItemRequest) -> PortfolioItemResponse:
    """Update a portfolio item."""
    try:
        pool = get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow("SELECT * FROM portfolio WHERE id = $1", item_id)
            if not row:
                raise HTTPException(status_code=404, detail="Portfolio item not found")

            updates = []
            params = []
            idx = 1

            if request.status is not None:
                updates.append(f"status = ${idx}")
                params.append(request.status.value)
                idx += 1
            if request.purchase_price is not None:
                updates.append(f"purchase_price = ${idx}")
                params.append(request.purchase_price)
                idx += 1
            if request.purchase_date is not None:
                updates.append(f"purchase_date = ${idx}")
                params.append(request.purchase_date)
                idx += 1
            if request.down_payment is not None:
                updates.append(f"down_payment = ${idx}")
                params.append(request.down_payment)
                idx += 1
            if request.mortgage_rate is not None:
                updates.append(f"mortgage_rate = ${idx}")
                params.append(request.mortgage_rate)
                idx += 1
            if request.current_rent is not None:
                updates.append(f"current_rent = ${idx}")
                params.append(request.current_rent)
                idx += 1
            if request.current_expenses is not None:
                updates.append(f"current_expenses = ${idx}")
                params.append(request.current_expenses)
                idx += 1
            if request.notes is not None:
                updates.append(f"notes = ${idx}")
                params.append(request.notes)
                idx += 1

            updates.append(f"updated_at = ${idx}")
            params.append(datetime.now(timezone.utc))
            idx += 1

            params.append(item_id)
            set_clause = ", ".join(updates)
            await conn.execute(
                f"UPDATE portfolio SET {set_clause} WHERE id = ${idx}",
                *params,
            )

            row = await conn.fetchrow("SELECT * FROM portfolio WHERE id = $1", item_id)

        return _row_to_response(row)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update portfolio item: {str(e)}")


@router.delete("/{item_id}", status_code=204)
async def remove_from_portfolio(item_id: str) -> None:
    """Remove a property from portfolio."""
    try:
        pool = get_pool()
        async with pool.acquire() as conn:
            result = await conn.execute("DELETE FROM portfolio WHERE id = $1", item_id)

        if result == "DELETE 0":
            raise HTTPException(status_code=404, detail="Portfolio item not found")

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to remove from portfolio: {str(e)}")


@router.post("/{item_id}/toggle-status", response_model=PortfolioItemResponse)
async def toggle_status(item_id: str) -> PortfolioItemResponse:
    """Toggle between owned and watching status."""
    try:
        pool = get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow("SELECT * FROM portfolio WHERE id = $1", item_id)
            if not row:
                raise HTTPException(status_code=404, detail="Portfolio item not found")

            new_status = "owned" if row["status"] == "watching" else "watching"
            await conn.execute(
                "UPDATE portfolio SET status = $1, updated_at = $2 WHERE id = $3",
                new_status, datetime.now(timezone.utc), item_id,
            )

            row = await conn.fetchrow("SELECT * FROM portfolio WHERE id = $1", item_id)

        return _row_to_response(row)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to toggle status: {str(e)}")
