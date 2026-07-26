.PHONY: help lint type test check check-oo update-oo check-coupling update-coupling check-suppressions update-suppressions check-dev-commands gen-dev-commands format build clean depot assert report

FUZZ      ?= fuzz
PROBCLI   ?= $(HOME)/Applications/ProB/probcli
SETSIZE   ?= 1
MAX_OPS   ?= 200
TIMEOUT   ?= 300000

# Specs ending in -bad.tex are intentional anti-pattern demonstrations
# excluded from quality gates. Only use this suffix for specs designed
# to demonstrate probcli animation failures.
SPECS     := $(filter-out %-bad.tex,$(wildcard examples/*.tex))
SPEC_NAMES := $(notdir $(basename $(SPECS)))

# ── Required targets (makefile.md) ──────────────────────────

help: ## Show available targets
	@grep -E '^[a-zA-Z_%-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  %-20s %s\n", $$1, $$2}'

lint: ## Lint markdown and Python
	npx markdownlint-cli2 "**/*.md" "#node_modules"
	uv run ruff check .
	uv run ruff format --check .

type: type-py $(addprefix type-z-,$(SPEC_NAMES)) ## Type-check Python and Z specs

type-py:
	uv run mypy src/ tests/
	uv run pyright src/ tests/

type-z-%: examples/%.tex
	@echo "fuzz $<"
	@$(FUZZ) -t $< > /dev/null 2>&1 && echo "  ✓ $*" || (echo "  ✗ $*"; $(FUZZ) -t $<; false)

test: test-py $(addprefix test-z-,$(SPEC_NAMES)) ## Run Python tests and model-check Z specs

test-py:
	uv run pytest tests/ -v

test-z-%: examples/%.tex
	@echo "probcli $< (setsize=$(SETSIZE))"
	@mkdir -p .tmp
	@$(PROBCLI) $< -model_check \
		-p DEFAULT_SETSIZE $(SETSIZE) \
		-p MAX_OPERATIONS $(MAX_OPS) \
		-p TIME_OUT $(TIMEOUT) \
		> .tmp/probcli-$*.out 2>&1; \
	rc=$$?; \
	grep -E "States analysed|Transitions fired|No counter|COUNTER|all open|not all" .tmp/probcli-$*.out | head -5; \
	echo ""; \
	exit $$rc

check: lint type test check-oo check-coupling check-suppressions check-dev-commands ## Run all quality gates

# ── Dev/prod plugin namespace ───────────────────────────────

gen-dev-commands: ## Regenerate commands/*-dev.md twins from prod sources
	uv run python tools/gen_dev_commands.py commands

check-dev-commands: ## Fail if any -dev twin is missing or out of sync
	uv run python tools/gen_dev_commands.py commands --check

# ── OO gate suite (ratchet against committed baselines) ─────
# Base-comparison flags injected by CI (e.g. --base-ref <merge-base>). Empty
# locally, where the tools default the base to `git merge-base origin/main HEAD`.
OO_BASE          ?=
COUPLING_BASE    ?=
SUPPRESSION_BASE ?=

check-oo: ## OO ratchet — must improve over baseline, never regress
	uv run python tools/oo_score.py src/punt_zspec/ --check $(OO_BASE)

update-oo: ## Update OO baseline (stage .oo-baseline.json and .oo-audit.jsonl)
	uv run python tools/oo_score.py src/punt_zspec/ --update $(OO_BASE)

check-coupling: ## Coupling ratchet — merge-base scoped, must not regress
	uv run python tools/oo_coupling.py src/punt_zspec/ --check $(COUPLING_BASE)

update-coupling: ## Update coupling baseline (stage baseline and audit jsonl)
	uv run python tools/oo_coupling.py src/punt_zspec/ --update $(COUPLING_BASE)

check-suppressions: ## Suppression ratchet — base-commit scoped, count must not rise
	uv run python tools/suppression_ratchet.py src/punt_zspec/ --check $(SUPPRESSION_BASE)

update-suppressions: ## Update suppression baseline
	uv run python tools/suppression_ratchet.py src/punt_zspec/ --update

format: ## Auto-format code
	uv run ruff format .
	uv run ruff check --fix .

build: ## Build wheel and sdist
	rm -rf dist/
	uv build
	uvx twine check dist/*

DEPOT := $(dir $(abspath $(lastword $(MAKEFILE_LIST))))../.depot

depot: build ## Build and copy wheel to local depot
	@mkdir -p $(DEPOT)
	@cp dist/*.whl $(DEPOT)/
	@echo "depot: $$(ls dist/*.whl | xargs -n1 basename) -> $(DEPOT)/"

# ── Optional targets ────────────────────────────────────────

assert: $(addprefix assert-,$(SPEC_NAMES)) ## CBC assertion check all specs

assert-%: examples/%.tex
	@echo "cbc_assertions $<"
	@mkdir -p .tmp
	@$(PROBCLI) $< -cbc_assertions \
		> .tmp/probcli-assert-$*.out 2>&1; \
	rc=$$?; \
	grep -E "counter|ASSERTION" .tmp/probcli-assert-$*.out | head -3; \
	echo ""; \
	exit $$rc

report: $(addprefix report-,$(SPEC_NAMES)) ## Generate reports for all specs
	-uv run python tools/oo_score.py src/punt_zspec/ --threshold

report-%: examples/%.tex
	@echo "report $<"
	@uv run z-spec test $< --setsize $(SETSIZE) --max-ops $(MAX_OPS) --timeout $(TIMEOUT) > /dev/null 2>&1 \
		&& echo "  ✓ $* (report saved)" || (echo "  ✗ $*"; false)

clean: ## Remove generated files
	@rm -f examples/*.fuzz examples/*.aux examples/*.log examples/*.out examples/*.toc examples/*.pdf
	@rm -f examples/*.report.json
	@rm -f ./*.aux ./*.log ./*.out ./*.toc
