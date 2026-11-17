from fastapi import FastAPI

from app.routers import disruptions, itineraries, recoveries

app = FastAPI(title="TripPatch")
app.include_router(recoveries.router)
app.include_router(disruptions.router)
app.include_router(itineraries.router)
