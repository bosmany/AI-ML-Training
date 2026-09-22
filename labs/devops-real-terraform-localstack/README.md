# Lab: Terraform-shaped infrastructure against a real LocalStack

Provision a small, real AWS-shaped stack - an S3 bucket, an IAM role with a least-privilege inline
policy, and a Lambda function - against a real [LocalStack](https://www.localstack.cloud/) container,
using the real `boto3` client API (no mocks, no `moto`). `terraform/main.tf` declares the exact same
stack in real HCL for a human who has `terraform` installed; the automated, pytest-graded part
re-creates it with the Python provisioner you write in `starter/lab/`, because a real `terraform`
binary is not assumed to be on every learner's or grader's machine, while `docker` already is.

## Why it matters in a real job

"We use LocalStack/moto in CI, but the on-call engineer still needs to reason about what `terraform
apply` actually calls." This lab is the missing middle step between "I wrote some HCL" and "I
understand the API calls underneath it": the same create-role-then-function ordering constraint, the
same idempotent-apply requirement, the same least-privilege IAM policy, and the same asynchronous
Lambda update behavior (a function can only have one update in flight at a time - a real race this
lab's own solution had to be fixed for) that trips people up against real AWS.

## Prerequisites (course chapters)

- [Infrastructure as code (Terraform)](../../devops/do05-infrastructure-as-code.html)
- [Cloud and container ops by example](../../devops/do04-cloud-and-container-ops.html)
- [Python for DevOps and APIs](../../python/ch07-python-devops-apis.html)
- `labs/devops-aws-audit-moto` (same `Finding`-shaped audit idea, against a whole fake account instead
  of one applied stack)

## Run it

```bash
cd labs/devops-real-terraform-localstack
python -m venv .venv && source .venv/bin/activate    # optional but recommended
pip install -r requirements.txt
pytest -q                        # starter: fails fast (NotImplementedError), no docker needed yet
LAB_TARGET=solution pytest -q    # maintainers / CI: starts a real LocalStack container and passes
```

**Requires Docker** (only for the `LAB_TARGET=solution` run, and for your own work once you start
implementing real network calls): `tests/conftest.py` starts one real `localstack/localstack:3.8.1`
container per test session on a random free host port, waits for its S3/IAM/Lambda/STS health check,
and tears it down afterward - even the extra sibling containers LocalStack's Lambda provider spins up
per function via the mounted Docker socket. If `docker` is not on `PATH`, the container-dependent
tests skip cleanly instead of failing. The plain unit tests (`test_client_and_packaging.py`) need no
container at all and run in milliseconds either way.

**Why 3.8.1 and not `latest`:** the `latest` LocalStack image now requires a `LOCALSTACK_AUTH_TOKEN`
(a free account, but a real sign-up) for services this lab uses; `3.8.1` predates that and is the
last fully-unauthenticated community image with a stable `S3`/`IAM`/`Lambda`/`STS` surface.

## What is provided vs what you write

Provided complete: `models.py` (the dataclasses - `StackConfig` mirrors `terraform/variables.tf`
one-to-one, `StackOutputs` mirrors `terraform/outputs.tf`), `terraform/main.tf` and friends (real,
correct HCL - see "Applying it for real" below), `terraform/lambda_src/handler.py` (the one real
Lambda function body, deployed both ways), and `tests/conftest.py` (container lifecycle - not part of
the lab's lesson).

You write, in `starter/lab/`: `client.py` (`make_clients`), `s3.py` (`ensure_bucket`), `iam.py`
(`_permissions_policy`, `ensure_lambda_role`), `lambda_.py` (`build_deployment_package`,
`_wait_until_ready`, `ensure_function`, `invoke`), `stack.py` (`apply_stack`), and `audit.py`
(`_audit_bucket`, `_audit_role`, `_audit_function`, `audit_stack`) - a small Python verifier in the
same style as `devops-aws-audit-moto`'s auditor, except it checks one already-applied stack for real
instead of scanning a whole fake account.

## Tasks

1. `make_clients`: three real boto3 clients (`s3`, `iam`, `lambda`) pointed at `cfg.endpoint_url`,
   with fake credentials, path-style S3 addressing, and a longer Lambda read timeout.
2. `ensure_bucket`: create-if-missing, then converge versioning, default AES256 encryption, and a
   full public access block - idempotently.
3. `_permissions_policy` + `ensure_lambda_role`: a trust policy scoped to `lambda.amazonaws.com`
   only, and an inline policy scoped to exactly this stack's bucket ARN - no bare `"*"` anywhere.
4. `build_deployment_package`: zip the handler file in memory with the right arcname.
5. `_wait_until_ready` + `ensure_function`: create-or-update, waiting for `State == "Active"` and
   `LastUpdateStatus == "Successful"` - and waiting *again* between `update_function_code` and
   `update_function_configuration` on the update path (see the hint below - this one is real).
6. `invoke`: synchronous invoke, decode the JSON payload, raise on `FunctionError`.
7. `apply_stack`: wire the above together in the only order that can work.
8. `audit_stack` and its three helpers: real checks against the real applied stack, returning the
   same `Finding(check, resource, severity, message, details)` shape as `devops-aws-audit-moto`.

## Hints

<details><summary>Why <code>make_clients</code> needs <code>addressing_style: "path"</code></summary>

LocalStack does not do virtual-hosted-style bucket DNS (`bucket.s3.amazonaws.com`); every S3 call
needs path-style (`s3.amazonaws.com/bucket`) or it fails to even resolve a host.
</details>

<details><summary>The idempotency requirement is not decorative</summary>

`tests/test_stack.py::test_apply_stack_is_idempotent` really calls `apply_stack` twice in a row and
asserts on the resulting object equality and on `list_buckets`/`list_functions`/`list_roles` counts -
exactly like running `terraform apply` twice with no diff in between. `iam.create_role` and
`lambda.create_function` both raise on a second call; catch `EntityAlreadyExists` /
`ResourceConflictException` specifically (never a bare `except Exception`) and fall back to
get-and-update.
</details>

<details><summary>The real race this lab's own solution needed a fix for</summary>

A Lambda function can only have one update in flight at a time. On the re-apply path, calling
`update_function_configuration` immediately after `update_function_code` - before the code update
has finished propagating - raises `ResourceConflictException: An update is in progress for
resource: ...`, even against LocalStack. This is not a hypothetical: it is exactly what broke the
first version of this lab's reference solution against a real container. Call `_wait_until_ready`
again between the two update calls, not just once at the very end.
</details>

<details><summary>IAM policy documents come back in two shapes</summary>

Depending on the SDK/backend version, `get_role_policy(...)["PolicyDocument"]` and
`get_role(...)["Role"]["AssumeRolePolicyDocument"]` can come back as an already-parsed `dict` or as
URL-encoded JSON (`_as_dict` in `audit.py` is provided and handles both - reuse it, don't
reimplement it).
</details>

<details><summary>Why the starter's tests never start a container</summary>

`tests/conftest.py`'s `localstack_endpoint` fixture only actually runs `docker run` when
`LAB_TARGET=solution`. Every starter function raises `NotImplementedError` before it makes any
network call, so paying for a real ~2-5s container startup on a run that must fail regardless would
be wasted time; `pytest -q` (starter) finishes in well under a second.
</details>

## Applying it for real (optional, not graded)

If you have `terraform >= 1.5`, the `aws` CLI v2, and `docker` installed, `terraform/main.tf`
declares the identical stack in real HCL, and `scripts/manual_verify.sh` runs the full real
lifecycle end to end against a real LocalStack container: `terraform init/plan/apply`,
`terraform show`, `aws ... get-bucket-versioning` / `get-bucket-encryption` /
`get-public-access-block` / `iam get-role` against the real `aws` CLI, a real `aws lambda invoke`,
and `terraform destroy`:

```bash
./scripts/manual_verify.sh
```

This script and `terraform/*.tf` are **not** exercised by `pytest` - the grading sandbox this lab was
built in does not have the `terraform` binary installed, only `docker`, so the automated, graded
contract in `tests/` re-implements the same three resources directly with boto3 (which is exactly
what the `AWS` Terraform provider itself does under the hood). Reading `terraform/main.tf` alongside
`starter/lab/` is worth doing either way: every boto3 call you write has a one-to-one HCL resource or
argument it corresponds to.

## Stretch goals

- Add a fourth resource (an SQS queue as a Lambda destination) end to end: HCL, Python provisioner,
  and an audit check for it.
- Make `apply_stack` diff-aware: return which resources were created vs. already-converged, the way
  `terraform apply`'s plan output distinguishes "1 to add" from "0 to change".
- Add a `--destroy` path to the Python provisioner (delete function, role policy + role, then empty
  and delete the bucket) and a test that a destroyed stack's resources are gone.
- Extend the audit to flag a Lambda whose `Environment` still points at a bucket that no longer
  exists (a dangling reference a `terraform plan` would not catch either).

## How this comes up in interviews

"Walk me through what `terraform apply` actually does when you run it against this Lambda module."
The real answer is the ordering constraint (role before function), the idempotency (a second apply is
a no-op), and the async gotchas (a function is not immediately invokable after creation, and it can
only have one update in flight at a time) - all three of which this lab makes you handle with boto3
directly instead of trusting Terraform's own retry/wait logic to paper over them.

## What this lab does not cover

- Terraform state itself (locking, remote backends, drift detection) - this lab applies a stack
  once per test with boto3 and never touches `.tfstate`.
- Multi-region, multi-account, or cross-stack references (remote state data sources, `terraform_
  remote_state`).
- IAM policy evaluation logic (`iam:SimulatePrincipalPolicy`) - the audit here does simple
  string/structure checks (wildcard resource, non-Lambda trust principal), not a real policy
  simulator.
- CI/CD wiring for `terraform plan` on pull requests - see `labs/fastapi-deploy-cicd` for the CI
  side of infrastructure changes.
