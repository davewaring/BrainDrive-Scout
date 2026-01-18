from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from scout.api.routes import router
from scout.config import get_settings

app = FastAPI(
    title="BrainDrive Scout",
    description="Resource review tool for analyzing external content against BrainDrive projects",
    version="0.1.0",
)

# CORS middleware for development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routes
app.include_router(router, prefix="/api")

# Serve static files (frontend)
# Try multiple paths: env var, /app/static (Docker), or relative to source
import os
static_paths = [
    os.environ.get("STATIC_DIR"),
    "/app/static",
    str(Path(__file__).parent.parent.parent / "static"),
]
for path in static_paths:
    if path and Path(path).exists():
        app.mount("/", StaticFiles(directory=path, html=True), name="static")
        break


def main():
    import uvicorn

    settings = get_settings()
    uvicorn.run(
        "scout.main:app",
        host=settings.host,
        port=settings.port,
        reload=True,
    )


if __name__ == "__main__":
    main()
