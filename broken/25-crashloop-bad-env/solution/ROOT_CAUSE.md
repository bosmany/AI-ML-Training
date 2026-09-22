# Root cause: invalid value for a required environment variable

**Cause.** `docker-compose.yml` set `WORKERS: "four"`. The service parses `WORKERS` with `int()` at startup and, by
design, refuses to start on invalid config (`config error: WORKERS must be an integer`, exit code 2).

**Why the symptoms.** The process exits within milliseconds of starting, so the `restart: unless-stopped` policy starts it
again, with a growing back-off. State flips between `Restarting` and `Up`, `RestartCount` climbs, the healthcheck never
passes and nothing listens. It is the Compose equivalent of Kubernetes `CrashLoopBackOff`. The image was fine: the
fault was configuration, which is why "same image, different behaviour". A restart policy hides a permanent
failure as a flapping one.

**Fix.** `WORKERS: "4"`. The fail-fast validation and the restart policy stay: the validation is what made the cause
visible in the first log line.

**Prevention.**
- Validate config in CI (`docker compose config`, plus running the service's own `--check` mode with the deploy's env).
- Alert on restart count / crash loops and on healthcheck failures; read `docker logs` and the exit code first.
- Keep types explicit in config files and document allowed ranges next to the variable.
