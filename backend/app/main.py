from fastapi import FastAPI

from app.routers import recoveries

app = FastAPI(title="TripPatch")
app.include_router(recoveries.router)
