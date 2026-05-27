from fastapi import APIRouter, Request, Depends
from fastapi.responses import RedirectResponse, JSONResponse
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Activity, Lap
from app.auth import get_current_coach
from app.utils import decrypt_garmin_password
import garth
from garth.exc import GarthHTTPError, GarthException
import logging

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/activities/{activity_id}")
async def activity_detail(
    request: Request, activity_id: int,
    db: Session = Depends(get_db), _=Depends(get_current_coach),
):
    activity = db.query(Activity).filter(Activity.id == activity_id).first()
    if not activity:
        return RedirectResponse("/", status_code=303)

    laps = db.query(Lap).filter(Lap.activity_id == activity_id).order_by(Lap.lap_number).all()
    laps_json = [
        {
            "lap_number": l.lap_number,
            "distance_m": l.distance_m,
            "duration_s": l.duration_s,
            "avg_pace_s_per_km": l.avg_pace_s_per_km,
            "avg_heart_rate": l.avg_heart_rate,
            "max_heart_rate": l.max_heart_rate,
            "avg_cadence": l.avg_cadence,
            "elevation_gain_m": l.elevation_gain_m,
        }
        for l in laps
    ]

    return request.app.state.templates.TemplateResponse(request, "activity_detail.html", {
        "activity": activity,
        "laps": laps_json,
    })


@router.get("/api/activities/{activity_id}/time-series")
async def activity_time_series(
    activity_id: int,
    db: Session = Depends(get_db),
    _=Depends(get_current_coach),
):
    activity = db.query(Activity).filter(Activity.id == activity_id).first()
    if not activity or not activity.athlete:
        return JSONResponse({"error": "not found"}, status_code=404)

    try:
        password = decrypt_garmin_password(activity.athlete.garmin_password_encrypted)
        client = garth.Client(domain="garmin.cn")
        client.login(activity.athlete.garmin_email, password)

        details = client.connectapi(
            f"/activity-service/activity/{activity.garmin_activity_id}/details",
            params={"maxChartSize": 2000},
        )

        metrics = []
        if isinstance(details, dict):
            metrics = details.get("activityDetailMetrics") or details.get("metrics") or []
        elif isinstance(details, list):
            metrics = details

        # Build index map from metricDescriptors
        descriptors = details.get("metricDescriptors", []) if isinstance(details, dict) else []
        idx = {}
        for d in descriptors:
            idx[d["key"]] = d["metricsIndex"]

        def val(key):
            i = idx.get(key)
            if i is None:
                return None
            return point[i] if i < len(point) else None

        result = []
        for item in metrics:
            point = item.get("metrics", item) if isinstance(item, dict) else item
            if not isinstance(point, list):
                continue

            speed = val("directSpeed")
            pace = round(1000.0 / speed, 1) if speed and speed > 0 else None
            raw_cadence = val("directRunCadence")
            cadence = round(raw_cadence * 2, 1) if raw_cadence else None

            stride = None
            if speed and speed > 0 and cadence and cadence > 0:
                stride = round((speed * 60 / cadence) * 100, 1)

            result.append({
                "time": val("sumElapsedDuration"),
                "heart_rate": val("directHeartRate"),
                "pace": pace,
                "cadence": cadence,
                "stride": stride,
            })

        return JSONResponse(result)
    except (GarthHTTPError, GarthException) as e:
        logger.warning("Time-series fetch failed for activity %s: %s", activity_id, e)
        return JSONResponse({"error": str(e)[:200]}, status_code=502)
    except Exception as e:
        logger.warning("Unexpected error fetching time-series for %s: %s", activity_id, e)
        return JSONResponse({"error": str(e)[:200]}, status_code=500)
