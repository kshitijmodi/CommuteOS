from fastapi import FastAPI

from .routers import auth, users

app = FastAPI(title="CommuteOS API", version="0.1.0")

app.include_router(auth.router)
app.include_router(users.router)


@app.get("/health")
def health():
    return {"status": "ok"}
