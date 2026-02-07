"""Portfolio management API endpoints."""

import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional, Literal
from enum import Enum

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

router = APIRouter()

# Storage location
DATA_DIR = Path("data")
PORTFOLIO_FILE = DATA_DIR / "portfolio.json"


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
    # Purchase details (for owned)
    purchase_price: Optional[int] = None
    purchase_date: Optional[str] = None
    down_payment: Optional[int] = None
    mortgage_rate: Optional[float] = None
    # Current performance (for owned)
    current_rent: Optional[int] = None
    current_expenses: Optional[int] = None
    # Notes
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
    # Calculated metrics for owned properties
    monthly_cash_flow: Optional[int] = None
    annual_return: Optional[float] = None
    equity: Optional[int] = None


class PortfolioListResponse(BaseModel):
    """Portfolio list response."""
    items: list[PortfolioItemResponse]
    count: int
    summary: dict


class PortfolioSummary(BaseModel):
    """Portfolio summary metrics."""
    total_owned: int
    total_watching: int
    total_invested: int
    total_equity: int
    monthly_cash_flow: int
    annual_cash_flow: int
    avg_return: float


def _ensure_data_dir():
    """Ensure data directory exists."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def _load_portfolio() -> dict:
    """Load portfolio from file."""
    _ensure_data_dir()
    if PORTFOLIO_FILE.exists():
        with open(PORTFOLIO_FILE, "r") as f:
            return json.load(f)
    return {"items": {}}


def _save_portfolio(data: dict):
    """Save portfolio to file."""
    _ensure_data_dir()
    with open(PORTFOLIO_FILE, "w") as f:
        json.dump(data, f, indent=2)


def _calculate_metrics(item: dict) -> dict:
    """Calculate performance metrics for owned properties."""
    metrics = {
        "monthly_cash_flow": None,
        "annual_return": None,
        "equity": None,
    }

    if item.get("status") != "owned":
        return metrics

    purchase_price = item.get("purchase_price")
    current_rent = item.get("current_rent")
    current_expenses = item.get("current_expenses", 0) or 0
    down_payment = item.get("down_payment")
    mortgage_rate = item.get("mortgage_rate")

    if purchase_price and current_rent:
        # Simple monthly cash flow (rent - expenses)
        # Note: doesn't include mortgage for simplicity
        monthly_cf = current_rent - current_expenses
        metrics["monthly_cash_flow"] = monthly_cf

        if down_payment:
            # Annual return on investment
            annual_cf = monthly_cf * 12
            annual_return = (annual_cf / down_payment) * 100 if down_payment > 0 else 0
            metrics["annual_return"] = round(annual_return, 2)

            # Rough equity estimate (down payment only, ignoring appreciation)
            metrics["equity"] = down_payment

    return metrics


def _item_to_response(item_id: str, item: dict) -> PortfolioItemResponse:
    """Convert stored item to response."""
    metrics = _calculate_metrics(item)
    return PortfolioItemResponse(
        id=item_id,
        property_id=item["property_id"],
        status=PortfolioStatus(item["status"]),
        address=item["address"],
        property_type=item["property_type"],
        purchase_price=item.get("purchase_price"),
        purchase_date=item.get("purchase_date"),
        down_payment=item.get("down_payment"),
        mortgage_rate=item.get("mortgage_rate"),
        current_rent=item.get("current_rent"),
        current_expenses=item.get("current_expenses"),
        notes=item.get("notes"),
        created_at=item["created_at"],
        updated_at=item["updated_at"],
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
        data = _load_portfolio()
        items = []

        for item_id, item in data.get("items", {}).items():
            if status and item.get("status") != status.value:
                continue
            items.append(_item_to_response(item_id, item))

        # Sort by updated_at descending
        items.sort(key=lambda x: x.updated_at, reverse=True)

        return PortfolioListResponse(
            items=items,
            count=len(items),
            summary=_calculate_summary(items),
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list portfolio: {str(e)}")


@router.post("", response_model=PortfolioItemResponse, status_code=201)
async def add_to_portfolio(request: CreatePortfolioItemRequest) -> PortfolioItemResponse:
    """Add a property to portfolio."""
    try:
        data = _load_portfolio()

        # Check if property already in portfolio
        for item_id, item in data.get("items", {}).items():
            if item["property_id"] == request.property_id:
                raise HTTPException(
                    status_code=400,
                    detail="Property already in portfolio"
                )

        item_id = str(uuid.uuid4())
        now = datetime.utcnow().isoformat()

        item = {
            "property_id": request.property_id,
            "status": request.status.value,
            "address": request.address,
            "property_type": request.property_type,
            "purchase_price": request.purchase_price,
            "purchase_date": request.purchase_date,
            "down_payment": request.down_payment,
            "mortgage_rate": request.mortgage_rate,
            "current_rent": request.current_rent,
            "current_expenses": request.current_expenses,
            "notes": request.notes,
            "created_at": now,
            "updated_at": now,
        }

        if "items" not in data:
            data["items"] = {}
        data["items"][item_id] = item
        _save_portfolio(data)

        return _item_to_response(item_id, item)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to add to portfolio: {str(e)}")


@router.get("/{item_id}", response_model=PortfolioItemResponse)
async def get_portfolio_item(item_id: str) -> PortfolioItemResponse:
    """Get a specific portfolio item."""
    try:
        data = _load_portfolio()
        item = data.get("items", {}).get(item_id)

        if not item:
            raise HTTPException(status_code=404, detail="Portfolio item not found")

        return _item_to_response(item_id, item)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get portfolio item: {str(e)}")


@router.put("/{item_id}", response_model=PortfolioItemResponse)
async def update_portfolio_item(item_id: str, request: UpdatePortfolioItemRequest) -> PortfolioItemResponse:
    """Update a portfolio item."""
    try:
        data = _load_portfolio()
        item = data.get("items", {}).get(item_id)

        if not item:
            raise HTTPException(status_code=404, detail="Portfolio item not found")

        # Update fields
        if request.status is not None:
            item["status"] = request.status.value
        if request.purchase_price is not None:
            item["purchase_price"] = request.purchase_price
        if request.purchase_date is not None:
            item["purchase_date"] = request.purchase_date
        if request.down_payment is not None:
            item["down_payment"] = request.down_payment
        if request.mortgage_rate is not None:
            item["mortgage_rate"] = request.mortgage_rate
        if request.current_rent is not None:
            item["current_rent"] = request.current_rent
        if request.current_expenses is not None:
            item["current_expenses"] = request.current_expenses
        if request.notes is not None:
            item["notes"] = request.notes

        item["updated_at"] = datetime.utcnow().isoformat()
        _save_portfolio(data)

        return _item_to_response(item_id, item)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update portfolio item: {str(e)}")


@router.delete("/{item_id}", status_code=204)
async def remove_from_portfolio(item_id: str) -> None:
    """Remove a property from portfolio."""
    try:
        data = _load_portfolio()

        if item_id not in data.get("items", {}):
            raise HTTPException(status_code=404, detail="Portfolio item not found")

        del data["items"][item_id]
        _save_portfolio(data)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to remove from portfolio: {str(e)}")


@router.post("/{item_id}/toggle-status", response_model=PortfolioItemResponse)
async def toggle_status(item_id: str) -> PortfolioItemResponse:
    """Toggle between owned and watching status."""
    try:
        data = _load_portfolio()
        item = data.get("items", {}).get(item_id)

        if not item:
            raise HTTPException(status_code=404, detail="Portfolio item not found")

        # Toggle status
        current = item["status"]
        item["status"] = "owned" if current == "watching" else "watching"
        item["updated_at"] = datetime.utcnow().isoformat()
        _save_portfolio(data)

        return _item_to_response(item_id, item)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to toggle status: {str(e)}")
