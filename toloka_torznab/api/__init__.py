from fastapi import FastAPI

from .toloka import router as toloka_router
from .utp import router as utp_router

app = FastAPI()
app.include_router(toloka_router)
app.include_router(utp_router)

__all__ = ["app"]
