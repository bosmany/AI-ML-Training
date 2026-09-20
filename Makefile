# One-command local environment for the labs. Works in Codespaces/devcontainer and on any machine with Python 3.11+.
# Usage: make bootstrap | doctor | labs | grade LAB=<lab-folder> | kind | kind-down | site-check
SHELL := /bin/bash
include versions.env
VENV ?= .venv
PY   := $(VENV)/bin/python
LABS := $(notdir $(patsubst %/,%,$(wildcard labs/*/)))

bootstrap: ## create .venv and install every lab's requirements
	python3 -m venv $(VENV)
	$(PY) -m pip install -q --upgrade pip
	@for d in labs/*/; do [ -f $$d/requirements.txt ] && $(PY) -m pip install -q -r $$d/requirements.txt || true; done
	@echo "bootstrap done -> make doctor"

doctor: ## show tool versions and what is missing
	@for t in python3 docker kubectl kind terraform node; do \
	  if command -v $$t >/dev/null 2>&1; then v=$$( [ $$t = kubectl ] && kubectl version --client 2>&1 | head -1 || $$t --version 2>&1 | head -1 ); printf "%-10s ok   %s\n" $$t "$$v"; \
	  else printf "%-10s MISSING (optional unless a lab needs it)\n" $$t; fi; done
	@[ -x $(PY) ] && echo "venv       ok   $(PY)" || echo "venv       MISSING -> make bootstrap"

labs: ## solution tests must pass, starter tests must all fail (all labs)
	PYTHON=$(abspath $(PY)) PYTHONDONTWRITEBYTECODE=1 bash labs/run_all.sh

grade: ## make grade LAB=devops-log-analyzer  -> run your starter tests; add TARGET=solution to check the reference
	@test -n "$(LAB)" || (echo "usage: make grade LAB=<one of: $(LABS)>"; exit 1)
	cd labs/$(LAB) && LAB_TARGET=$${TARGET:-starter} PYTHONDONTWRITEBYTECODE=1 ../../$(PY) -m pytest -q -p no:cacheprovider

kind: ## local Kubernetes cluster for k8s labs (needs docker)
	@command -v kind >/dev/null || (curl -sSLo /tmp/kind https://kind.sigs.k8s.io/dl/$(KIND_VERSION)/kind-linux-amd64 && sudo install /tmp/kind /usr/local/bin/kind)
	kind create cluster --name aiml --image $(KIND_NODE_IMAGE)
	kubectl cluster-info --context kind-aiml

kind-down:
	kind delete cluster --name aiml

site-check: ## HTML structure check for the course pages
	node scripts/verify-html.js

.PHONY: bootstrap doctor labs grade kind kind-down site-check
