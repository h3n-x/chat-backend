import asyncio
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.config import ALLOWED_ORIGINS
from app.routers import files, health, rooms, websocket
from app.security.rate_limiter import rate_limiter
from app.services.file_storage import file_storage

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("chat.main")


async def periodic_cleanup_task():
    """Background task to regularly purge expired files and rate limiter entries."""
    while True:
        try:
            await asyncio.sleep(120)  # Run every 2 minutes
            file_storage.cleanup_expired_files()
            rate_limiter.cleanup_stale_entries()
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"Error during periodic cleanup: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: start cleanup task
    logger.info("Initializing Chat Anónimo v2.0 Blind Relay...")
    task = asyncio.create_task(periodic_cleanup_task())
    yield
    # Shutdown: cancel cleanup task
    logger.info("Shutting down Chat Anónimo Blind Relay...")
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add defensive HTTP security headers to all responses."""

    async def dispatch(self, request: Request, call_next):
        response: Response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Cross-Origin-Opener-Policy"] = "same-origin"
        return response


def create_app() -> FastAPI:
    app = FastAPI(
        title="Chat Anónimo v2.0 Blind Relay",
        description="Zero-Knowledge, Zero-Persistence Blind Relay Backend for E2EE Ephemeral Communication",
        version="2.0.0",
        lifespan=lifespan,
    )

    # Defensive Security Headers
    app.add_middleware(SecurityHeadersMiddleware)

    # Explicit CORS Configuration
    app.add_middleware(
        CORSMiddleware,
        allow_origins=ALLOWED_ORIGINS,
        allow_credentials=True,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["*"],
    )

    # Register Route Handlers
    app.include_router(health.router)
    app.include_router(rooms.router)
    app.include_router(websocket.router)
    app.include_router(files.router)

    return app


app = create_app()
