"""Nightly report job: fingerprints the day's data (40 chunks of 3 MiB) with SHA-256 and prints one summary line."""
import hashlib
import resource

N_CHUNKS = 40
CHUNK = 3 * 1024 * 1024


def make_chunk(i):
    """Stand-in for reading one chunk of the day's data from storage."""
    return bytes([i % 256]) * CHUNK


def main():
    # Stream: one chunk in memory at a time (the working set is O(chunk), not O(day)).
    digest = hashlib.sha256()
    for i in range(N_CHUNKS):
        digest.update(make_chunk(i))
    peak_mb = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss // 1024
    print(f"DONE chunks={N_CHUNKS} sha256={digest.hexdigest()} peak_rss_mb={peak_mb}", flush=True)


if __name__ == "__main__":
    main()
