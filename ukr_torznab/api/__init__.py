from fastapi import FastAPI

from ukr_torznab.api.stats import router as stats_router
from ukr_torznab.api.toloka import router as toloka_router
from ukr_torznab.api.utp import router as utp_router

app = FastAPI()
app.include_router(toloka_router)
app.include_router(utp_router)
app.include_router(stats_router)

__all__ = ["app"]
