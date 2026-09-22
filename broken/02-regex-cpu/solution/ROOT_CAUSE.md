# Root cause: catastrophic backtracking (ReDoS) in two validators

**Cause.** `^([a-zA-Z0-9]+[._-]?)+$` and `^([\w-]+,?)*$` are a quantified group whose body can match the
same text in many ways: the separator is optional, so a run of `n` letters can be split between iterations of
the outer `+` in 2^(n-1) ways. When the input ends in a character the pattern cannot accept
(`"aaaa...a!"`), the engine tries every split before giving up: exponential time on a 40-character
string, with the GIL held, so one request pins a worker.

**Why the symptoms look the way they do.**
* Only odd inputs trigger it (a long run followed by a rejected character); valid names match at once.
* It takes one worker at 100% CPU with everything else healthy; the length limit (64/256) does not help
  because 2^40 is already forever.
* Each restart clears it until someone sends another such string (scanners and fuzzers do this routinely).

**Fix.** Make every step unambiguous, so there is exactly one way to match:
`^[a-zA-Z0-9]+(?:[._-][a-zA-Z0-9]+)*[._-]?$` (a run, then separator+run repeated, then an optional
trailing separator) and `^(?:[\w-]+(?:,[\w-]+)*,?)?$`. The verifier proves identical accept/reject with a
differential test on ~9,000 short strings. Band-aids that fail: capping the length (rejects valid names or
still explodes), truncating the input (accepts bad names), a timeout in a thread (the thread keeps burning CPU),
or blocking `!` (the next character breaks it). Possessive quantifiers / atomic groups (Python 3.11+) are
also valid fixes.

**Prevention.** ReDoS tests with adversarial inputs and a time bound (`tests/test_regression_redos.py`);
a linter (e.g. `regexploit`, `recheck`) in CI for user-facing patterns; use a linear-time engine
(RE2) for untrusted input; per-request CPU/time limits at the edge.
