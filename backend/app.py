from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, Response
from pathlib import Path

from .config.settings import settings
from .routes.video import router as video_router


app = FastAPI(title="VideoBrain Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files (frontend)
static_dir = Path(__file__).parent.parent / "frontend" / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

# Serve frontend HTML from root
frontend_dir = Path(__file__).parent.parent / "frontend"
if frontend_dir.exists():
    @app.get("/", include_in_schema=False)
    async def serve_frontend():
        """Serve the main frontend HTML file."""
        html_file = frontend_dir / "index.html"
        if html_file.exists():
            return FileResponse(html_file, media_type="text/html")
        return {"message": "Welcome to VideoBrain"}


@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    """Serve favicon or return a simple 204 No Content response"""
    favicon_path = static_dir / "favicon.ico"
    if favicon_path.exists():
        return FileResponse(favicon_path, media_type="image/x-icon")
    # Return 204 No Content to suppress browser favicon errors
    return Response(status_code=204)


@app.on_event("startup")
def startup_event():
    settings.ensure_dirs()


app.include_router(video_router, prefix="/videos")
