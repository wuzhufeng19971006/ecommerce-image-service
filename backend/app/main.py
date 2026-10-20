from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from .api import assets, gallery, jobs, meta
from .api.deps import ApiError
from .config import Settings, get_settings
from .db import create_database, init_db
from .services.runner import JobRunner
from .services.storage import Storage

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)


def create_app(settings: Settings | None = None) -> FastAPI:
    app_settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        logger.info("starting %s v%s", app_settings.app_name, app_settings.app_version)
        app.state.settings = app_settings
        engine, session_factory = create_database(app_settings)
        app.state.engine = engine
        app.state.session_factory = session_factory
        await init_db(engine)
        storage = Storage(app_settings.data_dir, app_settings.thumbnail_dimension)
        app.state.storage = storage
        runner = JobRunner(app_settings, session_factory, storage)
        app.state.runner = runner
        await runner.start()
        if app_settings.image_mock:
            logger.warning("IMAGE_MOCK=true: image generation is in demo mode")
        if not app_settings.is_configured:
            logger.warning("IMAGE_API_KEY is empty: generation is disabled")
        try:
            yield
        finally:
            await runner.stop()
            await engine.dispose()
            logger.info("application stopped")

    app = FastAPI(
        title=app_settings.app_name,
        version=app_settings.app_version,
        description="服装电商 AI 生图工作台",
        lifespan=lifespan,
        docs_url="/api/docs",
        redoc_url=None,
        openapi_url="/api/openapi.json",
    )
    app.state.settings = app_settings

    app.add_middleware(
        CORSMiddleware,
        allow_origins=app_settings.cors_origin_list,
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(meta.router, prefix="/api")
    app.include_router(assets.router, prefix="/api")
    app.include_router(jobs.router, prefix="/api")
    app.include_router(gallery.router, prefix="/api")

    @app.exception_handler(ApiError)
    async def api_error_handler(_request: Request, exc: ApiError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": {"code": exc.code, "message": exc.message}},
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(
        _request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        first = exc.errors()[0] if exc.errors() else {}
        location = ".".join(str(item) for item in first.get("loc", []) if item != "body")
        message = first.get("msg", "请求参数不完整")
        if location:
            message = f"{location}: {message}"
        return JSONResponse(
            status_code=422,
            content={"error": {"code": "VALIDATION_ERROR", "message": message}},
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_error_handler(
        _request: Request, exc: StarletteHTTPException
    ) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": {
                    "code": f"HTTP_{exc.status_code}",
                    "message": str(exc.detail),
                }
            },
        )

    @app.exception_handler(Exception)
    async def unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("unhandled error for %s %s", request.method, request.url.path)
        return JSONResponse(
            status_code=500,
            content={"error": {"code": "INTERNAL_ERROR", "message": "服务器内部错误"}},
        )

    dist = app_settings.frontend_dist
    if app_settings.serve_frontend and dist.is_dir():
        assets_dir = dist / "assets"
        if assets_dir.is_dir():
            app.mount("/assets", StaticFiles(directory=assets_dir), name="frontend-assets")

        @app.get("/{full_path:path}", include_in_schema=False)
        async def serve_frontend(full_path: str):
            if full_path.startswith("api/") or full_path == "api":
                return JSONResponse(
                    status_code=404,
                    content={"error": {"code": "NOT_FOUND", "message": "接口不存在"}},
                )
            candidate = (dist / full_path).resolve()
            if candidate.is_file() and candidate.is_relative_to(dist.resolve()):
                return FileResponse(candidate)
            return FileResponse(dist / "index.html")
    else:

        @app.get("/", include_in_schema=False)
        async def root() -> dict:
            return {
                "app": app_settings.app_name,
                "message": "后端已启动。前端开发地址：http://127.0.0.1:5173",
                "docs": "/api/docs",
            }

    return app


app = create_app()
