"""Chat Anónimo v2.0 - Application Entrypoint.

Provides a clean entrypoint for ASGI servers (Uvicorn, Hypercorn, Render, Docker).
"""
import uvicorn
from app.config import HOST, PORT
from app.main import app, create_app

__all__ = ["app", "create_app"]

if __name__ == "__main__":
    uvicorn.run("main:app", host=HOST, port=PORT, reload=False)
