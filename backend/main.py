"""
Aegis entry point.

Run with:
    PYTHONPATH=. python -m backend.main
    # or
    PYTHONPATH=. uvicorn backend.main:app --reload
"""

from __future__ import annotations

from .api.app import create_app
from .shared.config import get_settings

app = create_app()

if __name__ == "__main__":
    import uvicorn

    settings = get_settings()
    uvicorn.run(
        "backend.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.debug,
        log_config=None,  # Aegis configures its own logging
    )
