from fastapi import FastAPI, Request

from app.routers import disruptions, itineraries, places, plans, recoveries
from app.routers.deps import _client_ip

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


# TEMPORARY (2026-11-22): check which IP the guest limit sees behind Vercel + Render. Remove.
@app.get("/debug/ip", include_in_schema=False)
def debug_ip(request: Request) -> dict[str, str | None]:
    return {
        "seen": _client_ip(request),
        "x_forwarded_for": request.headers.get("x-forwarded-for"),
        "peer": request.client.host if request.client else None,
        "header_names": ",".join(sorted(request.headers.keys())),
        **{
            k: v
            for k, v in request.headers.items()
            if any(w in k for w in ("ip", "forwarded", "vercel", "cf-", "true-client"))
            and "signature" not in k
        },
    }
