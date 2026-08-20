"""认证活跃告警 API。"""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse

from super_ai.alerts.dependencies import get_alert_aggregator
from super_ai.alerts.models import ActiveAlertRecord
from super_ai.alerts.service import AlertAggregator
from super_ai.api_contracts import (
    ActiveAlert,
    ActiveAlertsData,
    AlertSource,
    FailureEnvelope,
    SuccessEnvelope,
)
from super_ai.api_responses import success_response
from super_ai.request_id import get_request_id
from super_ai.tenancy.context import CurrentUser
from super_ai.tenancy.dependencies import get_current_user

router = APIRouter(prefix="/aiops/alerts", tags=["aiops-alerts"])
RESPONSES: dict[int | str, dict[str, Any]] = {
    401: {"model": FailureEnvelope},
    403: {"model": FailureEnvelope},
    503: {"model": FailureEnvelope},
}


def _contract(record: ActiveAlertRecord) -> ActiveAlert:
    return ActiveAlert(
        alertName=record.alert_name,
        service=record.service,
        severity=record.severity,
        status=record.status,
        startsAt=record.starts_at,
        labels=record.labels,
        annotations=record.annotations,
        source=AlertSource(name=record.source.name, type=record.source.source_type),
        rawContext=record.raw_context,
    )


@router.get(
    "/active",
    operation_id="getActiveAlerts",
    response_model=SuccessEnvelope[ActiveAlertsData],
    responses=RESPONSES,
)
async def get_active_alerts(
    request: Request,
    _current_user: Annotated[CurrentUser, Depends(get_current_user)],
    aggregator: Annotated[AlertAggregator, Depends(get_alert_aggregator)],
) -> JSONResponse:
    alerts = await aggregator.list_active()
    return success_response(
        ActiveAlertsData(items=[_contract(item) for item in alerts]),
        get_request_id(request),
        exclude_none=False,
    )
