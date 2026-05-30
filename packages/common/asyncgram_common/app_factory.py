from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import cors_origins


def add_cors(app: FastAPI) -> None:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins(),
        allow_origin_regex=r"^http://192\.168\.\d{1,3}\.\d{1,3}:\d{2,5}$",
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )


def add_health(app: FastAPI) -> None:
    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}
