# Root cause: working set (~130 MiB) above the container's memory limit (96 MiB)

**Cause.** `report.py` loads the whole day's data (40 chunks x 3 MiB = 120 MiB, plus interpreter overhead) into a list before
hashing it, but the service is limited to `mem_limit: 96m` with swap disabled (`memswap_limit: 96m`).

**Why the symptoms.** When the cgroup's memory hits its limit and nothing can be reclaimed, the kernel OOM killer sends SIGKILL to
the process. There is no exception and no log line, because the process never gets to run any code; the exit
status is 128 + 9 = 137 and `docker inspect` shows `State.OOMKilled=true`. Laptops and small test samples do not hit the
limit; the host is not out of memory, only this cgroup is. `restart: always` just repeats the same crash.

**Fix (either is correct).** Reduce the footprint: stream the chunks, hashing each and discarding it (peak ~14 MiB, output
identical). Or right-size the limit above the measured working set plus headroom (e.g. `192m` with the matching
`memswap_limit`). Do not remove the limit, raise it to gigabytes, or disable the OOM killer: that moves the failure to the
whole host.

**Prevention.**
- Measure peak memory (this job prints `peak_rss_mb`) and set limits from measurements, with 20-30% headroom.
- Prefer streaming for data that scales with input size; add a memory-budget test with production-sized input.
- Alert on `OOMKilled` / exit code 137 and on memory usage approaching the limit (container_memory_working_set_bytes).
