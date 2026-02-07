"""Alerts CRUD API endpoints."""

from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from housemktanalyzr.alerts.criteria import AlertCriteria, CriteriaManager
from housemktanalyzr.models.property import PropertyType

router = APIRouter()

# Shared manager instance
manager = CriteriaManager()


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


def criteria_to_response(criteria: AlertCriteria) -> AlertResponse:
    """Convert AlertCriteria to AlertResponse."""
    return AlertResponse(
        id=criteria.id,
        name=criteria.name,
        enabled=criteria.enabled,
        regions=criteria.regions,
        property_types=[pt.value for pt in criteria.property_types],
        min_price=criteria.min_price,
        max_price=criteria.max_price,
        min_score=criteria.min_score,
        min_cap_rate=criteria.min_cap_rate,
        min_cash_flow=criteria.min_cash_flow,
        max_price_per_unit=criteria.max_price_per_unit,
        min_yield=criteria.min_yield,
        notify_email=criteria.notify_email,
        notify_on_new=criteria.notify_on_new,
        notify_on_price_drop=criteria.notify_on_price_drop,
        created_at=criteria.created_at.isoformat(),
        updated_at=criteria.updated_at.isoformat(),
        last_checked=criteria.last_checked.isoformat() if criteria.last_checked else None,
        last_match_count=criteria.last_match_count,
    )


@router.get("", response_model=AlertListResponse)
async def list_alerts(
    enabled_only: bool = Query(default=False, description="Only return enabled alerts"),
) -> AlertListResponse:
    """List all saved alerts.

    Returns all alert criteria, optionally filtered to enabled only.
    """
    try:
        if enabled_only:
            alerts = manager.get_enabled()
        else:
            alerts = manager.list_all()

        return AlertListResponse(
            alerts=[criteria_to_response(a) for a in alerts],
            count=len(alerts),
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list alerts: {str(e)}")


@router.post("", response_model=AlertResponse, status_code=201)
async def create_alert(request: CreateAlertRequest) -> AlertResponse:
    """Create a new alert.

    Creates a new alert criteria with the specified filters.
    """
    try:
        # Convert property type strings to enums
        property_types = []
        for pt in request.property_types:
            try:
                property_types.append(PropertyType(pt.upper()))
            except ValueError:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid property type: {pt}. Valid: HOUSE, DUPLEX, TRIPLEX, QUADPLEX, MULTIPLEX",
                )

        criteria = AlertCriteria(
            name=request.name,
            regions=request.regions,
            property_types=property_types,
            min_price=request.min_price,
            max_price=request.max_price,
            min_score=request.min_score,
            min_cap_rate=request.min_cap_rate,
            min_cash_flow=request.min_cash_flow,
            max_price_per_unit=request.max_price_per_unit,
            min_yield=request.min_yield,
            notify_email=request.notify_email,
            notify_on_new=request.notify_on_new,
            notify_on_price_drop=request.notify_on_price_drop,
        )

        manager.save(criteria)
        return criteria_to_response(criteria)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create alert: {str(e)}")


@router.get("/{alert_id}", response_model=AlertResponse)
async def get_alert(alert_id: str) -> AlertResponse:
    """Get a specific alert by ID."""
    try:
        criteria = manager.load(alert_id)

        if not criteria:
            raise HTTPException(status_code=404, detail="Alert not found")

        return criteria_to_response(criteria)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get alert: {str(e)}")


@router.put("/{alert_id}", response_model=AlertResponse)
async def update_alert(alert_id: str, request: UpdateAlertRequest) -> AlertResponse:
    """Update an existing alert.

    Only fields provided in the request will be updated.
    """
    try:
        criteria = manager.load(alert_id)

        if not criteria:
            raise HTTPException(status_code=404, detail="Alert not found")

        # Update fields if provided
        if request.name is not None:
            criteria.name = request.name
        if request.enabled is not None:
            criteria.enabled = request.enabled
        if request.regions is not None:
            criteria.regions = request.regions
        if request.property_types is not None:
            property_types = []
            for pt in request.property_types:
                try:
                    property_types.append(PropertyType(pt.upper()))
                except ValueError:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Invalid property type: {pt}",
                    )
            criteria.property_types = property_types
        if request.min_price is not None:
            criteria.min_price = request.min_price
        if request.max_price is not None:
            criteria.max_price = request.max_price
        if request.min_score is not None:
            criteria.min_score = request.min_score
        if request.min_cap_rate is not None:
            criteria.min_cap_rate = request.min_cap_rate
        if request.min_cash_flow is not None:
            criteria.min_cash_flow = request.min_cash_flow
        if request.max_price_per_unit is not None:
            criteria.max_price_per_unit = request.max_price_per_unit
        if request.min_yield is not None:
            criteria.min_yield = request.min_yield
        if request.notify_email is not None:
            criteria.notify_email = request.notify_email
        if request.notify_on_new is not None:
            criteria.notify_on_new = request.notify_on_new
        if request.notify_on_price_drop is not None:
            criteria.notify_on_price_drop = request.notify_on_price_drop

        manager.save(criteria)
        return criteria_to_response(criteria)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update alert: {str(e)}")


@router.delete("/{alert_id}", status_code=204)
async def delete_alert(alert_id: str) -> None:
    """Delete an alert by ID."""
    try:
        deleted = manager.delete(alert_id)

        if not deleted:
            raise HTTPException(status_code=404, detail="Alert not found")

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete alert: {str(e)}")


@router.post("/{alert_id}/toggle", response_model=AlertResponse)
async def toggle_alert(alert_id: str) -> AlertResponse:
    """Toggle alert enabled/disabled status."""
    try:
        criteria = manager.load(alert_id)

        if not criteria:
            raise HTTPException(status_code=404, detail="Alert not found")

        criteria.enabled = not criteria.enabled
        manager.save(criteria)
        return criteria_to_response(criteria)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to toggle alert: {str(e)}")
