import json
from typing import Literal

from fastapi import APIRouter, Query, Request, Response

from app.schemas import ApprovalRequest, ImportRequest, TaskRequest
from app.storage import repository_view

router = APIRouter()


def service(request: Request):
    return request.app.state.service


@router.get("/capabilities")
def capabilities(request: Request):
    settings = service(request).settings
    return {
        "model_configured": bool(settings.openai_api_key.get_secret_value()),
        "model": settings.model,
        "embedding": settings.embedding_provider,
        "sandbox_enabled": settings.sandbox_enabled,
        "queue": settings.execution_backend,
        "auth_required": bool(settings.api_token.get_secret_value()),
        "test_runner": "Python stdlib unittest only",
        "version": "0.2.0",
    }


@router.get("/repositories")
def repositories(request: Request):
    return service(request).repositories()


@router.post("/repositories", status_code=201)
def import_repository(body: ImportRequest, request: Request):
    return service(request).import_repository(body.url)


@router.get("/repositories/{repo_id}")
def repository(repo_id: str, request: Request):
    return repository_view(service(request).repository(repo_id))


@router.get("/repositories/{repo_id}/file")
def file(repo_id: str, request: Request, path: str = Query(max_length=250)):
    repo = service(request).repository(repo_id)
    if path not in repo.files:
        raise LookupError("File not found")
    return {"path": path, "content": repo.files[path], "commit": repo.commit}


@router.get("/repositories/{repo_id}/search")
def search(
    repo_id: str,
    request: Request,
    q: str = Query(min_length=1, max_length=1000),
    mode: Literal["keyword", "vector", "hybrid"] = "hybrid",
    limit: int = Query(5, ge=1, le=20),
):
    return service(request).retrieve(repo_id, q, mode, limit)


@router.get("/tasks")
def tasks(request: Request):
    return service(request).tasks()


@router.post("/tasks", status_code=201)
def create_task(body: TaskRequest, request: Request):
    app_service = service(request)
    task = app_service.create_task(body)
    app_service.schedule(task["id"])
    return task


@router.get("/tasks/{task_id}")
def task(task_id: str, request: Request):
    return service(request).task(task_id)


@router.post("/tasks/{task_id}/approval", status_code=202)
def approve(task_id: str, body: ApprovalRequest, request: Request):
    app_service = service(request)
    app_service.decide(task_id, body.model_dump())
    app_service.schedule(task_id)
    return app_service.task(task_id)


@router.post("/tasks/{task_id}/retry", status_code=202)
def retry(task_id: str, request: Request):
    app_service = service(request)
    app_service.retry(task_id)
    app_service.schedule(task_id)
    return app_service.task(task_id)


@router.get("/tasks/{task_id}/report")
def report(task_id: str, request: Request):
    data = json.dumps(service(request).task(task_id), ensure_ascii=False, indent=2)
    return Response(
        data,
        media_type="application/json",
        headers={
            "Content-Disposition": f'attachment; filename="devpilot-{task_id[:32]}.json"',
        },
    )


@router.get("/tasks/{task_id}/export")
def export(task_id: str, request: Request):
    return Response(
        service(request).export(task_id),
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="devpilot-{task_id[:32]}.zip"',
        },
    )
