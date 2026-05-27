from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse, JSONResponse
from starlette.middleware.sessions import SessionMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.templating import Jinja2Templates
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from app.config import SECRET_KEY, SYNC_INTERVAL_HOURS
from app.database import engine, Base, SessionLocal
from app.models import Coach  # noqa: ensure models loaded
from app.auth import hash_password
from app.utils import format_pace, format_duration, format_distance
from app.sync_engine import sync_all_athletes


class FlashMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        request.session.pop("flash_message", None)
        request.session.pop("flash_text", None)
        return response


def setup_templates(app: FastAPI):
    templates = Jinja2Templates(directory="templates")
    templates.env.filters["format_pace"] = format_pace
    templates.env.filters["format_duration"] = format_duration
    templates.env.filters["format_distance"] = format_distance
    app.state.templates = templates


def create_first_coach():
    db = SessionLocal()
    coach = db.query(Coach).first()
    if not coach:
        coach = Coach(
            username="admin",
            password_hash=hash_password("admin123"),
            display_name="教练",
        )
        db.add(coach)
        db.commit()
    db.close()


async def sync_job():
    db = SessionLocal()
    try:
        sync_all_athletes(db, sync_type="auto")
    finally:
        db.close()


scheduler = AsyncIOScheduler()


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    create_first_coach()
    scheduler.add_job(
        sync_job,
        trigger="interval",
        hours=SYNC_INTERVAL_HOURS,
        id="auto_sync",
        replace_existing=True,
    )
    scheduler.start()
    yield
    scheduler.shutdown()


app = FastAPI(lifespan=lifespan)


@app.exception_handler(HTTPException)
async def auth_exception_handler(request: Request, exc: HTTPException):
    if exc.status_code == 401:
        return RedirectResponse("/login", status_code=303)
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})


app.add_middleware(SessionMiddleware, secret_key=SECRET_KEY, same_site="lax", https_only=False)
app.add_middleware(FlashMiddleware)

setup_templates(app)
app.mount("/static", StaticFiles(directory="static"), name="static")

from app.routers import auth_router, dashboard_router, athlete_router, activity_router, sync_router
app.include_router(auth_router.router)
app.include_router(dashboard_router.router)
app.include_router(athlete_router.router)
app.include_router(activity_router.router)
app.include_router(sync_router.router)
