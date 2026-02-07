"""Alerts CRUD API endpoints backed by Postgres."""

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from ..db import get_pool

router = APIRouter()
logger = logging.getLogger(__name__)


class CreateAlertRequest(BaseModel):
    """Request body for creating an alert."""
    name: str = Field(min_length=1, max_length=100)
    regions: list[str] = Field(default_factory=list)
    property_types: list[str] = Field(default_factory=list)
    min_price: Optional[int] = Field(default=None, ge=0)
    max_price: Optional[int] = Field(default=None, ge=0)
    min_score: Optional[float] = Field(default=None, ge=0, le=100)
    min_cap_rate: Optional[float] = Field(default=None, ge=0)
    min_cash_flow: Optional[int] = Field(default=None)
    max_price_per_unit: Optional[int] = Field(default=None, ge=0)
    min_yield: Optional[float] = Field(default=None, ge=0)
    notify_email: Optional[str] = Field(default=None)
    notify_on_new: bool = Field(default=True)
    notify_on_price_drop: bool = Field(default=True)


class UpdateAlertRequest(BaseModel):
    """Request body for updating an alert."""
    name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    enabled: Optional[bool] = None
    regions: Optional[list[str]] = None
    property_types: Optional[list[str]] = None
    min_price: Optional[int] = Field(default=None, ge=0)
    max_price: Optional[int] = Field(default=None, ge=0)
    min_score: Optional[float] = Field(default=None, ge=0, le=100)
    min_cap_rate: Optional[float] = Field(default=None, ge=0)
    min_cash_flow: Optional[int] = None
    max_price_per_unit: Optional[int] = Field(default=None, ge=0)
    min_yield: Optional[float] = Field(default=None, ge=0)
    notify_email: Optional[str] = None
    notify_on_new: Optional[bool] = None
    notify_on_price_drop: Optional[bool] = None


class AlertResponse(BaseModel):
    """Alert criteria response."""
    id: str
    name: str
    enabled: bool
    regions: list[str]
    property_types: list[str]
    min_price: Optional[int]
    max_price: Optional[int]
    min_score: Optional[float]
    min_cap_rate: Optional[float]
    min_cash_flow: Optional[int]
    max_price_per_unit: Optional[int]
    min_yield: Optional[float]
    notify_email: Optional[str]
    notify_on_new: bool
    notify_on_price_drop: bool
    created_at: str
    updated_at: str
    last_checked: Optional[str]
    last_match_count: int


class AlertListResponse(BaseModel):
    """List of alerts response."""
    alerts: list[AlertResponse]
    count: int


def _row_to_response(row) -> AlertResponse:
    """Convert a database row to AlertResponse."""
    return AlertResponse(
        id=row["id"],
        name=row["name"],
        enabled=row["enabled"],
        regions=json.loads(row["regions"]) if isinstance(row["regions"], str) else row["regions"],
        property_types=json.loads(row["property_types"]) if isinstance(row["property_types"], str) else row["property_types"],
        min_price=row["min_price"],
        max_price=row["max_price"],
        min_score=row["min_score"],
        min_cap_rate=row["min_cap_rate"],
        min_cash_flow=row["min_cash_flow"],
        max_price_per_unit=row["max_price_per_unit"],
        min_yield=row["min_yield"],
        notify_email=row["notify_email"],
        notify_on_new=row["notify_on_new"],
        notify_on_price_drop=row["notify_on_price_drop"],
        created_at=row["created_at"].isoformat() if row["created_at"] else "",
        updated_at=row["updated_at"].isoformat() if row["updated_at"] else "",
        last_checked=row["last_checked"].isoformat() if row["last_checked"] else None,
        last_match_count=row["last_match_count"] or 0,
    )


@router.get("", response_model=AlertListResponse)
async def list_alerts(
    enabled_only: bool = Query(default=False, description="Only return enabled alerts"),
) -> AlertListResponse:
    """List all saved alerts."""
    try:
        pool = get_pool()
        async with pool.acquire() as conn:
            if enabled_only:
                rows = await conn.fetch(
                    "SELECT * FROM alerts WHERE enabled = TRUE ORDER BY name"
                )
            else:
                rows = await conn.fetch("SELECT * FROM alerts ORDER BY name")

        alerts = [_row_to_response(row) for row in rows]
        return AlertListResponse(alerts=alerts, count=len(alerts))

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list alerts: {str(e)}")


@router.post("", response_model=AlertResponse, status_code=201)
async def create_alert(request: CreateAlertRequest) -> AlertResponse:
    """Create a new alert."""
    try:
        pool = get_pool()
        alert_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)

        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO alerts (
                    id, name, enabled, regions, property_types,
                    min_price, max_price, min_score, min_cap_rate,
                    min_cash_flow, max_price_per_unit, min_yield,
                    notify_email, notify_on_new, notify_on_price_drop,
                    created_at, updated_at
                ) VALUES (
                    $1, $2, TRUE, $3::jsonb, $4::jsonb,
                    $5, $6, $7, $8, $9, $10, $11,
                    $12, $13, $14, $15, $15
                )
                """,
                alert_id, request.name,
                json.dumps(request.regions),
                json.dumps(request.property_types),
                request.min_price, request.max_price,
                request.min_score, request.min_cap_rate,
                request.min_cash_flow, request.max_price_per_unit,
                request.min_yield, request.notify_email,
                request.notify_on_new, request.notify_on_price_drop,
                now,
            )

            row = await conn.fetchrow("SELECT * FROM alerts WHERE id = $1", alert_id)

        return _row_to_response(row)

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create alert: {str(e)}")


@router.get("/{alert_id}", response_model=AlertResponse)
async def get_alert(alert_id: str) -> AlertResponse:
    """Get a specific alert by ID."""
    try:
        pool = get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow("SELECT * FROM alerts WHERE id = $1", alert_id)

        if not row:
            raise HTTPException(status_code=404, detail="Alert not found")

        return _row_to_response(row)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get alert: {str(e)}")


@router.put("/{alert_id}", response_model=AlertResponse)
async def update_alert(alert_id: str, request: UpdateAlertRequest) -> AlertResponse:
    """Update an existing alert."""
    try:
        pool = get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow("SELECT * FROM alerts WHERE id = $1", alert_id)
            if not row:
                raise HTTPException(status_code=404, detail="Alert not found")

            # Build SET clause dynamically
            updates = []
            params = []
            idx = 1

            if request.name is not None:
                updates.append(f"name = ${idx}")
                params.append(request.name)
                idx += 1
            if request.enabled is not None:
                updates.append(f"enabled = ${idx}")
                params.append(request.enabled)
                idx += 1
            if request.regions is not None:
                updates.append(f"regions = ${idx}::jsonb")
                params.append(json.dumps(request.regions))
                idx += 1
            if request.property_types is not None:
                updates.append(f"property_types = ${idx}::jsonb")
                params.append(json.dumps(request.property_types))
                idx += 1
            if request.min_price is not None:
                updates.append(f"min_price = ${idx}")
                params.append(request.min_price)
                idx += 1
            if request.max_price is not None:
                updates.append(f"max_price = ${idx}")
                params.append(request.max_price)
                idx += 1
            if request.min_score is not None:
                updates.append(f"min_score = ${idx}")
                params.append(request.min_score)
                idx += 1
            if request.min_cap_rate is not None:
                updates.append(f"min_cap_rate = ${idx}")
                params.append(request.min_cap_rate)
                idx += 1
            if request.min_cash_flow is not None:
                updates.append(f"min_cash_flow = ${idx}")
                params.append(request.min_cash_flow)
                idx += 1
            if request.max_price_per_unit is not None:
                updates.append(f"max_price_per_unit = ${idx}")
                params.append(request.max_price_per_unit)
                idx += 1
            if request.min_yield is not None:
                updates.append(f"min_yield = ${idx}")
                params.append(request.min_yield)
                idx += 1
            if request.notify_email is not None:
                updates.append(f"notify_email = ${idx}")
                params.append(request.notify_email)
                idx += 1
            if request.notify_on_new is not None:
                updates.append(f"notify_on_new = ${idx}")
                params.append(request.notify_on_new)
                idx += 1
            if request.notify_on_price_drop is not None:
                updates.append(f"notify_on_price_drop = ${idx}")
                params.append(request.notify_on_price_drop)
                idx += 1

            # Always update timestamp
            updates.append(f"updated_at = ${idx}")
            params.append(datetime.now(timezone.utc))
            idx += 1

            params.append(alert_id)
            set_clause = ", ".join(updates)
            await conn.execute(
                f"UPDATE alerts SET {set_clause} WHERE id = ${idx}",
                *params,
            )

            row = await conn.fetchrow("SELECT * FROM alerts WHERE id = $1", alert_id)

        return _row_to_response(row)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update alert: {str(e)}")


@router.delete("/{alert_id}", status_code=204)
async def delete_alert(alert_id: str) -> None:
    """Delete an alert by ID."""
    try:
        pool = get_pool()
        async with pool.acquire() as conn:
            result = await conn.execute("DELETE FROM alerts WHERE id = $1", alert_id)

        if result == "DELETE 0":
            raise HTTPException(status_code=404, detail="Alert not found")

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete alert: {str(e)}")


@router.post("/{alert_id}/toggle", response_model=AlertResponse)
async def toggle_alert(alert_id: str) -> AlertResponse:
    """Toggle alert enabled/disabled status."""
    try:
        pool = get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow("SELECT * FROM alerts WHERE id = $1", alert_id)
            if not row:
                raise HTTPException(status_code=404, detail="Alert not found")

            new_enabled = not row["enabled"]
            await conn.execute(
                "UPDATE alerts SET enabled = $1, updated_at = $2 WHERE id = $3",
                new_enabled, datetime.now(timezone.utc), alert_id,
            )

            row = await conn.fetchrow("SELECT * FROM alerts WHERE id = $1", alert_id)

        return _row_to_response(row)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to toggle alert: {str(e)}")
