import os

from fastapi import FastAPI

from app.routers import disruptions, itineraries, me, places, plans, recoveries

# The interactive API docs stay on for local runs and off on the host (Render sets RENDER):
# they list every route and schema to anyone. The spec for the frontend's types is read from
# app.openapi() directly (frontend/scripts/gen-api.mjs), so it does not need the routes.
_PUBLIC_DOCS = not os.environ.get("RENDER")

app = FastAPI(
    title="TripPatch",
    docs_url="/docs" if _PUBLIC_DOCS else None,
    redoc_url="/redoc" if _PUBLIC_DOCS else None,
    openapi_url="/openapi.json" if _PUBLIC_DOCS else None,
)
app.include_router(recoveries.router)
app.include_router(disruptions.router)
app.include_router(itineraries.router)
app.include_router(places.router)
app.include_router(plans.router)
app.include_router(me.router)


@app.get("/health", include_in_schema=False)
def health() -> dict[str, str]:
    """For the host's health check: answers without touching the LLM, Google or the database,
    so a slow outside service never gets a healthy server restarted."""
    return {"status": "ok"}
