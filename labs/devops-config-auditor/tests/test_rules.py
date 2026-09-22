"""Each rule against true positives AND look-alike false positives."""

from __future__ import annotations

from helpers import compose, k8s, run_rule
from lab.rules import (
    MissingProbes,
    NoExposedPorts,
    NoLatestTag,
    NoPlaintextSecrets,
    NoPrivileged,
    ResourceLimits,
)


def pointers(findings) -> list[str]:  # noqa: ANN001
    return [f.path for f in findings]


def test_latest_tag_flags_latest_and_untagged_images_but_not_pinned_look_alikes() -> None:
    bad = ["nginx", "nginx:latest", "nginx:LATEST", "registry.local:5000/app"]  # a registry port is not a tag
    for image in bad:
        found = run_rule(NoLatestTag, compose(f"image: {image}"))
        assert pointers(found) == ["/services/app/image"], f"{image!r} should be flagged"
        assert found[0].rule_id == "no-latest-tag" and found[0].line == 3
    good = ["nginx:1.27", "registry.local:5000/app:1.2", "nginx@sha256:" + "a" * 64, "${IMAGE}", "latest-tools:1.0"]
    for image in good:
        assert run_rule(NoLatestTag, compose(f"image: '{image}'")) == [], f"{image!r} must not be flagged"
    assert run_rule(NoLatestTag, k8s("image: myorg/api:1.0")) == []
    assert pointers(run_rule(NoLatestTag, k8s("image: myorg/api"))) == ["/spec/template/spec/containers/0/image"]


def test_resource_limits_compose_and_kubernetes() -> None:
    assert pointers(run_rule(ResourceLimits, compose("image: a:1"))) == ["/services/app"]
    assert run_rule(ResourceLimits, compose("image: a:1\nmem_limit: 64m")) == []
    assert run_rule(ResourceLimits, compose("deploy:\n  resources:\n    limits:\n      memory: 1g")) == []
    assert pointers(run_rule(ResourceLimits, compose("deploy:\n  resources:\n    reservations:\n      memory: 1g"))) == [
        "/services/app"
    ], "reservations are not limits"
    none = run_rule(ResourceLimits, k8s("image: a:1"))
    assert pointers(none) == ["/spec/template/spec/containers/0"]
    cpu_only = run_rule(ResourceLimits, k8s("resources:\n  limits:\n    cpu: 1"))
    assert pointers(cpu_only) == ["/spec/template/spec/containers/0/resources/limits"]
    assert "memory" in cpu_only[0].message and "cpu" not in cpu_only[0].message
    assert run_rule(ResourceLimits, k8s("resources:\n  limits:\n    cpu: 1\n    memory: 1Gi")) == []


def test_probes_are_required_for_services_but_not_for_jobs() -> None:
    assert pointers(run_rule(MissingProbes, compose("image: a:1"))) == ["/services/app"]
    assert pointers(run_rule(MissingProbes, compose("healthcheck:\n  disable: true"))) == ["/services/app"]
    assert run_rule(MissingProbes, compose("healthcheck:\n  test: ['CMD', 'true']")) == []
    both_missing = run_rule(MissingProbes, k8s("image: a:1"))
    assert len(both_missing) == 1 and "livenessProbe" in both_missing[0].message and "readinessProbe" in both_missing[0].message
    only_live = run_rule(MissingProbes, k8s("livenessProbe:\n  exec: {command: [true]}"))
    assert len(only_live) == 1 and "readinessProbe" in only_live[0].message and "livenessProbe" not in only_live[0].message
    assert run_rule(MissingProbes, k8s("image: a:1", kind="Job")) == [], "run-to-completion Jobs need no probes"


def test_privileged_containers_are_critical_but_false_and_missing_are_fine() -> None:
    found = run_rule(NoPrivileged, compose("privileged: true"))
    assert pointers(found) == ["/services/app/privileged"] and found[0].severity.label == "critical"
    assert run_rule(NoPrivileged, compose("privileged: false")) == []
    assert run_rule(NoPrivileged, compose("image: a:1")) == []
    assert pointers(run_rule(NoPrivileged, k8s("securityContext:\n  privileged: true"))) == [
        "/spec/template/spec/containers/0/securityContext/privileged"
    ]
    assert run_rule(NoPrivileged, k8s("securityContext:\n  privileged: false\n  runAsNonRoot: true")) == []


def test_plaintext_secrets_in_compose_environment_map_and_list() -> None:
    found = run_rule(NoPlaintextSecrets, compose("environment:\n  DB_PASSWORD: hunter2\n  API_KEY: abc\n  LOG_LEVEL: debug"))
    assert pointers(found) == ["/services/app/environment/DB_PASSWORD", "/services/app/environment/API_KEY"]
    listed = run_rule(NoPlaintextSecrets, compose("environment:\n  - POSTGRES_PASSWORD=s3cret\n  - MODE=prod"))
    assert pointers(listed) == ["/services/app/environment/0"]
    assert [f.line for f in listed] == [4]
    fine = """
        environment:
          DB_PASSWORD: ${DB_PASSWORD}
          API_TOKEN: $API_TOKEN
          POSTGRES_PASSWORD_FILE: /run/secrets/pw
          TOKEN_ENABLED: true
          SECRET_PATH: /etc/secret
          EMPTY_PASSWORD: ""
          PASSTHROUGH_TOKEN:
    """
    assert run_rule(NoPlaintextSecrets, compose(fine)) == []
    assert run_rule(NoPlaintextSecrets, compose("environment:\n  - DB_PASSWORD\n  - X_TOKEN=${X_TOKEN}")) == []


def test_plaintext_secrets_in_kubernetes_env_ignores_secret_refs() -> None:
    env = """
        env:
          - name: API_TOKEN
            value: abc123
          - name: DB_PASSWORD
            valueFrom:
              secretKeyRef: {name: db, key: password}
          - name: LOG_LEVEL
            value: info
    """
    found = run_rule(NoPlaintextSecrets, k8s(env))
    assert pointers(found) == ["/spec/template/spec/containers/0/env/0/value"]
    assert found[0].severity.label == "high"


def test_exposed_ports_compose_short_and_long_syntax() -> None:
    exposed = ['"8080:80"', '"80"', '"0.0.0.0:8080:80"', '"8080:80/udp"', "8080", '"[::]:8080:80"']
    for port in exposed:
        assert pointers(run_rule(NoExposedPorts, compose(f"ports:\n  - {port}"))) == ["/services/app/ports/0"], port
    loopback = ['"127.0.0.1:8080:80"', '"[::1]:8080:80"', '"localhost:8080:80"']
    for port in loopback:
        assert run_rule(NoExposedPorts, compose(f"ports:\n  - {port}")) == [], f"{port} is loopback only"
    assert run_rule(NoExposedPorts, compose("expose:\n  - '8080'")) == [], "expose does not publish to the host"
    assert pointers(run_rule(NoExposedPorts, compose("ports:\n  - target: 80\n    published: 8080"))) == ["/services/app/ports/0"]
    assert run_rule(NoExposedPorts, compose("ports:\n  - target: 80\n    published: 8080\n    host_ip: 127.0.0.1")) == []


def test_exposed_ports_kubernetes_only_flags_host_port() -> None:
    assert run_rule(NoExposedPorts, k8s("ports:\n  - containerPort: 8080")) == []
    found = run_rule(NoExposedPorts, k8s("ports:\n  - containerPort: 8080\n    hostPort: 8080"))
    assert pointers(found) == ["/spec/template/spec/containers/0/ports/0"]
