from fastapi import FastAPI

from app.routers import disruptions, itineraries, places, plans, recoveries

app = FastAPI(title="TripPatch")
app.include_router(recoveries.router)
app.include_router(disruptions.router)
app.include_router(itineraries.router)
app.include_router(places.router)
app.include_router(plans.router)


@app.get("/health", include_in_schema=False)
def health() -> dict[str, str]:
    """For the host's health check: answers without touching the LLM, Google or the database,
    so a slow outside service never gets a healthy server restarted."""
    return {"status": "ok"}
