# Report worker: operating targets

* Retained heap growth after the 40,000-request soak (`loadgen.py`) stays under **8 MB**.
* The 200 most popular queries are served from cache at least **80%** of the time.
* Two spellings of the same query ("  Foo  BAR " and "foo bar") return the same report.
