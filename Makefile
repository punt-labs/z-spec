.PHONY: help lint type test check format assert report clean

FUZZ      ?= fuzz
PROBCLI   ?= $(HOME)/Applications/ProB/probcli
SETSIZE   ?= 1
MAX_OPS   ?= 200
TIMEOUT   ?= 300000

SPECS     := $(wildcard examples/*.tex)
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
	uv run pyright

type-z-%: examples/%.tex
	@echo "fuzz $<"
	@$(FUZZ) -t $< > /dev/null 2>&1 && echo "  ✓ $*" || (echo "  ✗ $*"; $(FUZZ) -t $<; false)

test: test-py $(addprefix test-z-,$(SPEC_NAMES)) ## Run Python tests and model-check Z specs

test-py:
	uv run pytest tests/ -v

test-z-%: examples/%.tex
	@echo "probcli $< (setsize=$(SETSIZE))"
	@$(PROBCLI) $< -model_check \
		-p DEFAULT_SETSIZE $(SETSIZE) \
		-p MAX_OPERATIONS $(MAX_OPS) \
		-p TIME_OUT $(TIMEOUT) \
		2>&1 | grep -E "States analysed|Transitions fired|No counter|COUNTER|all open|not all" | head -5
	@echo ""

check: lint type test ## Run all quality gates

format: ## Auto-format code
	uv run ruff format .
	uv run ruff check --fix .

# ── Optional targets ────────────────────────────────────────

assert: $(addprefix assert-,$(SPEC_NAMES)) ## CBC assertion check all specs

assert-%: examples/%.tex
	@echo "cbc_assertions $<"
	@$(PROBCLI) $< -cbc_assertions 2>&1 | grep -E "counter|ASSERTION" | head -3
	@echo ""

report: $(addprefix report-,$(SPEC_NAMES)) ## Generate reports for all specs

report-%: examples/%.tex
	@echo "report $<"
	@uv run z-spec test $< --setsize $(SETSIZE) --max-ops $(MAX_OPS) --timeout $(TIMEOUT) > /dev/null 2>&1 \
		&& echo "  ✓ $* (report saved)" || (echo "  ✗ $*"; false)

clean: ## Remove generated files
	@rm -f examples/*.fuzz examples/*.aux examples/*.log examples/*.out examples/*.toc examples/*.pdf
	@rm -f examples/*.report.json
	@rm -f ./*.aux ./*.log ./*.out ./*.toc
