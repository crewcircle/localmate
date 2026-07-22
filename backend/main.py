import logging
from contextlib import asynccontextmanager

import sentry_sdk
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import settings
from db import init_db
from scheduler import create_scheduler
from routers import auth, webhooks, drafts

logging.basicConfig(level=logging.INFO)

if settings.sentry_dsn:
    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        environment=settings.environment,
        traces_sample_rate=0.1,
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    app.state.scheduler = None
    app.state.arq = None

    role = settings.worker_role
    if role == "scheduler":
        # Dedicated single-active scheduler container: enqueue-only APScheduler
        # + an arq pool to push jobs. NOT HA — must be a single instance (C4).
        from task_queue import get_arq_pool

        app.state.arq = await get_arq_pool()
        scheduler = create_scheduler()
        scheduler.start()
        app.state.scheduler = scheduler
        logging.getLogger(__name__).info("Started enqueue-only scheduler (role=scheduler)")
    else:
        # web role: create an arq pool for enqueuing from request handlers.
        # Do NOT start APScheduler here (prevents duplicate cron fire across
        # web replicas). The 'worker' role runs via the arq CLI, not uvicorn.
        from task_queue import get_arq_pool

        try:
            app.state.arq = await get_arq_pool()
        except Exception as e:
            logging.getLogger(__name__).warning("arq pool init failed (web role): %s", e)

    yield

    if app.state.scheduler is not None:
        app.state.scheduler.shutdown()
    if app.state.arq is not None:
        try:
            await app.state.arq.close()
        except Exception:
            pass


app = FastAPI(title="LocalMate", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://localmate.crewcircle.com.au",
        "https://localmate.crewcircle.co",
        "http://localhost:3000",
        "http://localhost:3001",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/auth")
app.include_router(webhooks.router, prefix="/webhooks")
app.include_router(drafts.router, prefix="/drafts")
try:
    from routers import approve
    app.include_router(approve.router, prefix="/approve")
except ImportError:
    pass


@app.get("/health")
async def health():
    return {"status": "ok", "project": settings.project_id}
