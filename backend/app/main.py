from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routers import (
    auth,
    home_office,
    preferences,
    recommendations,
    trip_outcomes,
    trips,
    users,
)

app = FastAPI(title="CommuteOS API", version="0.1.0")

# Wide open for now - the mobile app is the only client and Phase 1/2 have
# no browser-based frontend. Revisit if a web client is ever added.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(users.router)
app.include_router(trips.router)
app.include_router(preferences.router)
app.include_router(recommendations.router)
app.include_router(trip_outcomes.router)
app.include_router(home_office.router)


@app.get("/health")
def health():
    return {"status": "ok"}
