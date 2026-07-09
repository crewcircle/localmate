from contextlib import asynccontextmanager

from fastapi import FastAPI

from db import init_db
from scheduler import create_scheduler
from routers import auth, webhooks, drafts


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    scheduler = create_scheduler()
    scheduler.start()
    app.state.scheduler = scheduler
    yield
    scheduler.shutdown()


app = FastAPI(title="Local Biz Automation", lifespan=lifespan)

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
    return {"status": "ok", "project": "local-biz-au"}
