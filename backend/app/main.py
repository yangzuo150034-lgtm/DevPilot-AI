import secrets
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app.api.health import router as health_router
from app.api.platform import router as platform_router
from app.core.config import Settings
from app.service import Service


def create_app(settings: Settings | None = None) -> FastAPI:
    configuration = settings or Settings()

    @asynccontextmanager
    async def lifespan(application):
        application.state.service = Service(configuration)
        yield
        application.state.service.close()

    application = FastAPI(
        title="DevPilot AI API",
        version="0.2.0",
        lifespan=lifespan,
        description="Repository analysis, code retrieval, approval and sandbox workflow.",
    )
    application.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=[
            "127.0.0.1",
            "localhost",
            "testserver",
            "backend",
        ],
    )

    @application.middleware("http")
    async def authenticate(request: Request, call_next):
        if request.url.path != "/api/v1/health":
            token = configuration.api_token.get_secret_value()
            if token:
                supplied = request.headers.get("authorization", "")
                if not secrets.compare_digest(supplied, "Bearer " + token):
                    return JSONResponse({"detail": "API token required"}, status_code=401)
            elif request.client and request.client.host not in {"127.0.0.1", "::1", "testclient"}:
                return JSONResponse(
                    {"detail": "Configure an API token for non-loopback clients"}, status_code=403
                )
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        return response

    @application.exception_handler(ValueError)
    async def bad_request(request, error):
        return JSONResponse({"detail": str(error)}, status_code=400)

    @application.exception_handler(LookupError)
    async def not_found(request, error):
        return JSONResponse({"detail": str(error)}, status_code=404)

    @application.exception_handler(httpx.HTTPError)
    async def upstream_error(request, error):
        return JSONResponse(
            {"detail": "Upstream service unavailable; retry later"}, status_code=502
        )

    application.include_router(health_router, prefix="/api/v1")
    application.include_router(platform_router, prefix="/api/v1")
    return application


app = create_app()
