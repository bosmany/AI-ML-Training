# Lab: AWS Account Auditor (boto3 against moto)

Write a security/hygiene auditor with the **real** `boto3` client API and run it against `moto`, an in-process
fake AWS. It finds untagged or long-stopped EC2 instances, security groups open to the world, S3 buckets without
default encryption or public access block, and IAM users without MFA or with old access keys - and produces a
JSON and a Markdown report.

## Why it matters in a real job

Every cloud team runs some version of this script (or buys it as a product). What separates a toy from something
you can run against production: pagination (results beyond page 1 are where the problems hide), throttling
(`Throttling`, `RequestLimitExceeded`) handled with backoff instead of a crash, `AccessDenied` on one service not
hiding the findings from the others, an injected clock so the "older than 90 days" logic is testable, and no
possibility of touching a real account while testing.

## Prerequisites (course chapters)

- [Cloud and container ops by example](../../devops/do04-cloud-and-container-ops.html)
- [Automation scripts and resilience](../../devops/do03-automation-scripts-resilience.html)
- [Python for DevOps and APIs](../../python/ch07-python-devops-apis.html)
- [Config and data formats](../../devops/do02-config-yaml-json-toml.html) (JSON reports)

## Run it

```bash
cd labs/devops-aws-audit-moto
python -m venv .venv && source .venv/bin/activate    # optional but recommended
pip install -r requirements.txt
pytest -q                        # starter: every test fails until you implement it
LAB_TARGET=solution pytest -q    # maintainers / CI: the reference solution passes
```

**Safety:** `tests/conftest.py` sets fake credentials and region for every test, points `AWS_CONFIG_FILE` /
`AWS_SHARED_CREDENTIALS_FILE` at nothing, removes `AWS_PROFILE` and endpoint overrides, and wraps each test in
`moto.mock_aws()`. Nothing in this lab can reach a real AWS account. Keep it that way in your own code: never
hard-code credentials, always take clients as parameters.

## What is provided vs what you write

Provided: the dataclasses (`AuditConfig`, `Finding`, `AuditError`, `AuditResult`, `AuditReport`), the retryable
error-code list and `error_code`. You write `client.py` (`make_client`, `is_retryable`, `retry_call`, `list_all`),
`ec2.py`, `s3.py`, `iam.py` and `report.py`.

## Tasks

1. `retry_call`: exponential backoff (`base * 2**n`, capped) for retryable `ClientError`s only, injectable `sleep`.
2. `list_all`: collect every page with a boto3 paginator; a throttle mid-listing must restart it without duplicates.
3. EC2: `ec2-untagged` (missing/empty required tag) and `ec2-stopped-too-long` (strictly more than N days; compute from `now`, never `datetime.now()`).
4. Security groups: `sg-open-ingress` for `0.0.0.0/0` **and** `::/0` on sensitive ports, including port ranges and protocol `-1`.
5. S3: no default encryption; missing or partial public access block. Not-configured is a *finding*, `AccessDenied` is an *error*.
6. IAM: users without MFA; ACTIVE access keys older than N days (boundary is strictly greater).
7. `run_audit` + `to_json` + `to_markdown`: one failing service becomes an entry in `errors`, the rest still run.

## Hints

<details><summary>Why tests inject `now` and `sleep`</summary>

`AuditConfig(now=..., sleep=...)` - a check that calls `datetime.now()` or `time.sleep()` cannot be tested
deterministically. Naive datetimes are rejected: comparing naive and aware values is a classic silent bug.
</details>

<details><summary>Stopped time of an instance</summary>

EC2 does not return "stopped at". Parse `StateTransitionReason`, e.g. `User initiated (2024-01-01 12:00:00 GMT)`
(moto writes `UTC`, real AWS writes `GMT`; accept both). An instance that was never stopped has an empty reason.
</details>

<details><summary>Paginators and `PageSize`</summary>

`client.get_paginator("describe_instances").paginate(PaginationConfig={"PageSize": 5})`. EC2 paginates by
*reservation*, and real EC2 requires `MaxResults >= 5`. Put the whole `for page in ...` loop inside the function you
pass to `retry_call`; retrying only the failed `next()` would repeat or skip items.
</details>

<details><summary>Security-group rule shape</summary>

Each `IpPermissions` entry has `IpProtocol`, `FromPort`, `ToPort`, `IpRanges` (IPv4) and `Ipv6Ranges`. Protocol
`"-1"` has **no** ports. Numeric protocols `"6"`/`"17"` mean tcp/udp.
</details>

<details><summary>Not-configured vs error in S3</summary>

Codes `ServerSideEncryptionConfigurationNotFoundError` and `NoSuchPublicAccessBlockConfiguration` mean "this bucket
is not configured" - report a finding. Any other code (e.g. `AccessDenied`) means you could not look: report an
error, never claim the bucket is unprotected.
</details>

<details><summary>Why botocore's own retries are switched off in `make_client`</summary>

So that throttling reaches *your* retry logic (with an injectable sleep) instead of botocore sleeping silently.
In real projects you would normally keep botocore's `standard` retry mode and add only what it does not cover.
</details>

## Stretch goals

- Add a `--region` fan-out (`describe_regions`) and audit every region; think about per-region API quotas.
- Check for unencrypted EBS volumes and public RDS snapshots.
- Add jitter to `retry_call` (see the backup-janitor lab) and honour `Retry-After` style hints.
- Turn the auditor into a CLI with a `--fail-on high` exit code for CI.
- Assume an audit role with `sts.assume_role` and run across several accounts (moto supports `sts`).

## How this comes up in interviews

"Write a script that finds security groups open to the world." Then: *what about IPv6? port ranges? protocol -1?*
(the three misses), *what if there are 10,000 instances?* (pagination), *what if the API throttles you?*
(backoff, jitter, idempotent retry), *how do you test it without an AWS account?* (moto / stubbers, injected
clock), *what if you lack permission for S3?* (report it, keep going).

## What this lab does not cover

- **moto does not paginate everything.** In moto 5.x only `DescribeInstances` really returns multiple pages; IAM
  `ListUsers`, S3 `ListBuckets` and `DescribeSecurityGroups` return everything at once. Those paths are tested with
  botocore's `Stubber` (scripted pages), which proves your token handling but not AWS's real page sizes.
- IAM checks are per-user API calls: fine for hundreds of users, but production tools use the credential report
  (`generate_credential_report`) instead.
- Since 2023 S3 encrypts every new object with SSE-S3 by default; the "no default encryption" check here means "no
  *explicit* configuration" (e.g. no enforced KMS key). Real audits also inspect bucket policies and ACLs.
- Single region and single account; no cross-region S3 redirects; no real IAM policy evaluation.
- Findings are a starting point, not a compliance framework (CIS, SOC 2 need far more).
