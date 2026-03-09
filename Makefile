FUZZ      ?= fuzz
PROBCLI   ?= $(HOME)/Applications/ProB/probcli
SETSIZE   ?= 1
MAX_OPS   ?= 200
TIMEOUT   ?= 300000

SPECS     := $(wildcard examples/*.tex)
SPEC_NAMES := $(notdir $(basename $(SPECS)))

# ── Type-check ──────────────────────────────────────────────

.PHONY: check check-%

check: $(addprefix check-,$(SPEC_NAMES))  ## Type-check all specs with fuzz

check-%: examples/%.tex
	@echo "fuzz $<"
	@$(FUZZ) -t $< > /dev/null 2>&1 && echo "  ✓ $*" || (echo "  ✗ $*"; $(FUZZ) -t $<; false)

# ── Model-check ─────────────────────────────────────────────

.PHONY: test test-%

test: $(addprefix test-,$(SPEC_NAMES))  ## Model-check all specs with probcli

test-%: examples/%.tex
	@echo "probcli $< (setsize=$(SETSIZE))"
	@$(PROBCLI) $< -model_check \
		-p DEFAULT_SETSIZE $(SETSIZE) \
		-p MAX_OPERATIONS $(MAX_OPS) \
		-p TIME_OUT $(TIMEOUT) \
		2>&1 | grep -E "States analysed|Transitions fired|No counter|COUNTER|all open|not all" | head -5
	@echo ""

# ── Assertions ──────────────────────────────────────────────

.PHONY: assert assert-%

assert: $(addprefix assert-,$(SPEC_NAMES))  ## CBC assertion check all specs

assert-%: examples/%.tex
	@echo "cbc_assertions $<"
	@$(PROBCLI) $< -cbc_assertions 2>&1 | grep -E "counter|ASSERTION" | head -3
	@echo ""

# ── Convenience ─────────────────────────────────────────────

.PHONY: all clean help

all: check assert test  ## Run all checks: fuzz + assertions + model-check

clean:  ## Remove generated files
	@rm -f examples/*.fuzz examples/*.aux examples/*.log examples/*.out examples/*.toc examples/*.pdf

help:  ## Show this help
	@grep -E '^[a-zA-Z_%-]+:.*?## ' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  %-20s %s\n", $$1, $$2}'
