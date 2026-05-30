from fastapi import FastAPI

from asyncgram_common.app_factory import add_cors, add_health

from .routes import router

app = FastAPI(title="Asyncgram Admin Service")
add_cors(app)
add_health(app)
app.include_router(router)
