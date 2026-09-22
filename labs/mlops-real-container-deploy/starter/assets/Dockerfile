# TODO: this Dockerfile builds and runs, but it has real problems a platform-team review would
# reject. Fix it (see README task 2). Rules being checked, all real production concerns:
#   1. multi-stage build (separate the training/build step from the slim runtime image)
#   2. base image pinned to an exact version tag, not a floating major-only tag
#   3. non-root USER in the final stage
#   4. a real HEALTHCHECK that calls /health, with explicit --interval/--timeout
#   5. no secrets baked into ENV/ARG
#   6. requirements.txt copied and installed BEFORE the rest of the source (layer caching)
#   7. pip install --no-cache-dir (or ENV PIP_NO_CACHE_DIR=1)
#   8. exec-form CMD (a JSON array), not shell form
#   9. ENV PYTHONUNBUFFERED=1 and PYTHONDONTWRITEBYTECODE=1
#  10. EXPOSE the port, and bind uvicorn to 0.0.0.0 (not its 127.0.0.1 default) so the container is
#      actually reachable from outside itself once you run it with `docker run -p`

FROM python:3-slim

# Someone hard-coded a "just for now" token instead of reading it from the environment.
ENV MODEL_REGISTRY_TOKEN=hunter2-not-a-real-secret-but-shaped-like-one

WORKDIR /srv
COPY . .
RUN pip install -r requirements.txt

RUN python train_model.py

CMD uvicorn app.main:app --port 8000
