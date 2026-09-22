"""Small HTTP service configured from the environment (12-factor style). Fails fast on bad config."""
import os
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer


class ConfigError(Exception):
    pass


def load_config(env=os.environ):
    try:
        workers = int(env.get("WORKERS", ""))
    except ValueError:
        raise ConfigError(f"WORKERS must be an integer, got {env.get('WORKERS')!r}") from None
    if not 1 <= workers <= 16:
        raise ConfigError(f"WORKERS must be between 1 and 16, got {workers}")
    port = int(env.get("PORT", "8000"))
    return {"workers": workers, "port": port}


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        body = b"ok\n"
        self.send_response(200 if self.path in ("/", "/healthz") else 404)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):  # keep the container log readable
        pass


def main(argv):
    try:
        cfg = load_config()
    except ConfigError as e:
        print(f"config error: {e}", file=sys.stderr, flush=True)
        return 2
    if "--check" in argv:
        return 0
    print(f"ready workers={cfg['workers']} port={cfg['port']}", flush=True)
    HTTPServer(("0.0.0.0", cfg["port"]), Handler).serve_forever()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
