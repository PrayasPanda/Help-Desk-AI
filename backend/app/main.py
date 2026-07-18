import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import ai
from .config import settings
from .db import Base, engine
from .realtime import broker
from .routers import auth, metrics, tickets

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(engine)
    broker.loop = asyncio.get_running_loop()
    ai.build_vector_store()
    yield


app = FastAPI(title="QuickDesk API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(tickets.router)
app.include_router(metrics.router)


@app.get("/health")
def health():
    return {"status": "ok", "llm": "groq" if settings.groq_api_key else "mock"}
