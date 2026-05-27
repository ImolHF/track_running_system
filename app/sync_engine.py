from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from app.models import Athlete, Activity, Lap, SyncLog
from app.utils import decrypt_garmin_password
from app.config import INITIAL_SYNC_DAYS
import logging

import garth
from garth.exc import GarthHTTPError, GarthException

logger = logging.getLogger(__name__)


def _create_client(email: str, password: str):
    client = garth.Client(domain="garmin.cn")
    client.login(email, password)
    return client


def _fetch_since(client, start_date: datetime) -> list[dict]:
    """Fetch all activities since start_date using pagination.

    The list endpoint returns activities in reverse chronological order.
    We paginate until we see an activity older than start_date.
    """
    activities = []
    start = 0
    limit = 200

    while True:
        params = {"start": start, "limit": limit}
        batch = client.connectapi(
            "/activitylist-service/activities/search/activities",
            params=params,
        )
        if not batch or not isinstance(batch, list) or len(batch) == 0:
            break

        for act in batch:
            act_time = _parse_time(act.get("startTimeLocal"))
            if act_time and act_time >= start_date:
                activities.append(act)
            # Activities are in reverse-chronological order, so once we
            # see one before start_date the rest are also too old.
            elif act_time:
                return activities

        if len(batch) < limit:
            break
        start += limit

    return activities


def sync_athlete(athlete: Athlete, db: Session, sync_type: str = "manual") -> SyncLog:
    log = SyncLog(
        athlete_id=athlete.id,
        sync_type=sync_type,
        status="running",
        started_at=datetime.utcnow(),
        finished_at=datetime.utcnow(),
    )
    db.add(log)
    db.commit()

    try:
        password = decrypt_garmin_password(athlete.garmin_password_encrypted)
        client = _create_client(athlete.garmin_email, password)

        now = datetime.utcnow()
        start_date = athlete.last_synced_at or (now - timedelta(days=INITIAL_SYNC_DAYS))

        activities = _fetch_since(client, start_date)
        new_count = 0

        for garmin_act in activities:
            garmin_id = garmin_act.get("activityId")
            if not garmin_id:
                continue

            if db.query(Activity).filter(Activity.garmin_activity_id == garmin_id).first():
                continue

            activity_type_dto = garmin_act.get("activityType") or {}
            type_key = activity_type_dto.get("typeKey", "") if isinstance(activity_type_dto, dict) else ""

            if type_key and "running" not in type_key.lower() and type_key not in ("", "uncategorized"):
                continue

            # Core fields come from the list item (always present).
            start_time = _parse_time(garmin_act.get("startTimeLocal"))
            distance_m = _float_or_none(garmin_act.get("distance"))
            duration_s = _float_or_none(garmin_act.get("duration"))

            if not start_time:
                continue

            # Fetch detail for extended metrics (non-fatal if it fails).
            detail = None
            summary = {}
            try:
                detail = client.connectapi(f"/activity-service/activity/{garmin_id}")
                if isinstance(detail, dict):
                    summary = detail.get("summaryDTO") or {}
            except (GarthHTTPError, GarthException):
                pass

            activity = Activity(
                athlete_id=athlete.id,
                garmin_activity_id=garmin_id,
                name=garmin_act.get("activityName", ""),
                activity_type=type_key or "running",
                start_time=start_time,
                end_time=start_time + timedelta(seconds=duration_s) if duration_s else None,
                distance_m=distance_m,
                duration_s=duration_s,
                elapsed_duration_s=_float_or_none(garmin_act.get("elapsedDuration")),
                avg_heart_rate=_int_or_none(
                    summary.get("averageHR") or garmin_act.get("averageHR")
                ),
                max_heart_rate=_int_or_none(
                    summary.get("maxHR") or garmin_act.get("maxHR")
                ),
                avg_cadence=_float_or_none(
                    summary.get("averageRunCadence")
                    or garmin_act.get("averageRunningCadenceInStepsPerMinute")
                ),
                avg_stride_length_cm=_float_or_none(
                    summary.get("strideLength") or garmin_act.get("avgStrideLength")
                ),
                elevation_gain_m=_float_or_none(
                    summary.get("elevationGain") or garmin_act.get("elevationGain")
                ),
                elevation_loss_m=_float_or_none(
                    summary.get("elevationLoss") or garmin_act.get("elevationLoss")
                ),
                calories=_int_or_none(
                    summary.get("calories") or garmin_act.get("calories")
                ),
                avg_temperature_c=_float_or_none(summary.get("averageTemperature")),
                training_effect_aerobic=_float_or_none(
                    summary.get("aerobicTrainingEffect")
                    or summary.get("trainingEffect")
                    or garmin_act.get("aerobicTrainingEffect")
                ),
                training_effect_anaerobic=_float_or_none(
                    summary.get("anaerobicTrainingEffect")
                    or garmin_act.get("anaerobicTrainingEffect")
                ),
                vo2max=_float_or_none(
                    (detail or {}).get("vO2MaxValue") or garmin_act.get("vO2MaxValue")
                ),
            )

            if activity.distance_m and activity.duration_s and activity.distance_m > 0:
                activity.avg_pace_s_per_km = activity.duration_s / (activity.distance_m / 1000)

            db.add(activity)
            db.flush()

            try:
                splits_data = client.connectapi(
                    f"/activity-service/activity/{garmin_id}/splits"
                )
                for split in _iter_splits(splits_data):
                    speed_ms = _float_or_none(split.get("averageSpeed"))
                    lap_pace = (1000.0 / speed_ms) if speed_ms and speed_ms > 0 else None
                    lap = Lap(
                        activity_id=activity.id,
                        lap_number=_int_or_none(split.get("lapIndex")) or 0,
                        distance_m=_float_or_none(split.get("distance")),
                        duration_s=_float_or_none(split.get("duration")),
                        avg_pace_s_per_km=lap_pace,
                        avg_heart_rate=_int_or_none(split.get("averageHR")),
                        max_heart_rate=_int_or_none(split.get("maxHR")),
                        avg_cadence=_float_or_none(split.get("averageRunCadence")),
                        elevation_gain_m=_float_or_none(split.get("elevationGain")),
                    )
                    db.add(lap)
            except (GarthHTTPError, GarthException) as e:
                logger.warning("Failed to fetch splits for activity %s: %s", garmin_id, e)
            except Exception as e:
                logger.warning("Unexpected error saving splits for activity %s: %s", garmin_id, e)

            db.commit()
            new_count += 1

        total = db.query(Activity).filter(Activity.athlete_id == athlete.id)
        athlete.total_activities = total.count()
        athlete.total_distance_km = round(
            sum((a.distance_m or 0) for a in total.all()) / 1000, 1
        )
        athlete.last_synced_at = datetime.utcnow()
        db.commit()

        log.status = "success"
        log.activities_fetched = new_count

    except GarthHTTPError as e:
        db.rollback()
        log.status = "failed"
        log.error_message = f"连接失败：{str(e)[:400]}"
    except GarthException as e:
        db.rollback()
        log.status = "failed"
        log.error_message = f"认证失败：{str(e)[:400]}"
    except Exception as e:
        db.rollback()
        log.status = "failed"
        log.error_message = f"{type(e).__name__}: {str(e)[:400]}"

    log.finished_at = datetime.utcnow()
    db.commit()
    return log


def sync_all_athletes(db: Session, sync_type: str = "auto") -> list[SyncLog]:
    athletes = db.query(Athlete).filter(Athlete.is_active == True).all()
    logs = []
    for athlete in athletes:
        log = sync_athlete(athlete, db, sync_type)
        logs.append(log)
    return logs


def _iter_splits(splits_data):
    """Yield split dicts from whatever shape the splits endpoint returns.

    CN endpoint returns {"activityId": int, "lapDTOs": [...], "eventDTOs": [...]}.
    Fall back to iterating a plain list if that changes.
    """
    if isinstance(splits_data, list):
        yield from splits_data
    elif isinstance(splits_data, dict):
        lap_dtos = splits_data.get("lapDTOs")
        if isinstance(lap_dtos, list):
            yield from lap_dtos


def _parse_time(val):
    if not val:
        return None
    try:
        return datetime.fromisoformat(str(val).replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None


def _float_or_none(val):
    if val is None:
        return None
    try:
        return float(val)
    except (TypeError, ValueError):
        return None


def _int_or_none(val):
    if val is None:
        return None
    try:
        return int(float(val))
    except (TypeError, ValueError):
        return None
