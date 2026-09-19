"""The tiny service you are shipping. (Provided - do not edit.)"""

import os

from fastapi import FastAPI

app = FastAPI(title="candidate-api")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "env": os.environ.get("APP_ENV", "development")}
