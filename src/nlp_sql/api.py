from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from nlp_sql.deps import get_app_config
from nlp_sql.routers import auth, data, nlp, schema

FRONTEND_DIR = Path(__file__).resolve().parents[2] / "frontend"


def _cors_origins() -> list[str]:
    try:
        return get_app_config().server.cors_origins
    except Exception:
        return ["http://127.0.0.1:8000", "http://localhost:8000"]


def create_app() -> FastAPI:
    app = FastAPI(
        title="NLP SQL Data Generator",
        version="0.3.0",
        description=(
            "Chat UI and APIs only — databases are reached through the secured data gateway, "
            "never from the browser or the LLM directly."
        ),
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=_cors_origins(),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(auth.router, prefix="/v1/auth", tags=["authorization"])
    app.include_router(schema.router, prefix="/v1/schema", tags=["schema"])
    app.include_router(data.router, prefix="/v1/data", tags=["data"])
    app.include_router(nlp.router, prefix="/v1/nlp", tags=["nlp"])

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    serve_ui = True
    try:
        serve_ui = get_app_config().server.serve_chat_ui
    except Exception:
        pass

    if serve_ui and FRONTEND_DIR.is_dir():
        assets = FRONTEND_DIR / "assets"
        if assets.is_dir():
            app.mount("/assets", StaticFiles(directory=assets), name="assets")

        index = FRONTEND_DIR / "index.html"

        @app.get("/", include_in_schema=False)
        @app.get("/chat", include_in_schema=False)
        def chat_page() -> FileResponse:
            return FileResponse(index)

    return app


app = create_app()
