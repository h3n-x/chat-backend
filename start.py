#!/usr/bin/env python3
"""Startup script for Render / Cloud hosting."""
import os
import uvicorn
from app.config import HOST

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(
        "main:app",
        host=HOST,
        port=port,
        log_level="info",
        access_log=True,
    )
