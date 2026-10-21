"""Run with python -m app.worker. RQ mode requires shared data/config with the API."""

from app.core.config import Settings
from app.service import Service


def run_task(task_id: str):
    service = Service(Settings())
    try:
        service.execute(task_id)
    finally:
        service.close()


def main():
    from redis import Redis
    from rq import Queue, SimpleWorker

    settings = Settings()
    if not settings.redis_url:
        raise SystemExit("Set DEVPILOT_REDIS_URL first")
    connection = Redis.from_url(settings.redis_url)
    SimpleWorker([Queue("devpilot", connection=connection)], connection=connection).work()


if __name__ == "__main__":
    main()
