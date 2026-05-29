.PHONY: smoke test benchmark schema-check validate-demo public-check install-skill package-check

smoke:
	bash scripts/run_smoke_test.sh

test:
	python -m unittest discover -s tests

benchmark:
	python scripts/run_statebind_benchmark.py \
		--data data/statebind_guard_seed_benchmark.json \
		--card docs/result_cards/statebind_guard_seed_benchmark.md \
		--json docs/result_cards/statebind_guard_seed_benchmark_metrics.json \
		--title Seed
	python scripts/run_statebind_benchmark.py \
		--data data/statebind_guard_natural_handoff_benchmark.json \
		--card docs/result_cards/statebind_guard_natural_handoff_benchmark.md \
		--json docs/result_cards/statebind_guard_natural_handoff_benchmark_metrics.json \
		--title "Natural Handoff"

schema-check:
	python statebind_handoff/statebind_handoff.py schema --out /tmp/statebind.schema.json >/dev/null
	diff -u schemas/statebind.schema.json /tmp/statebind.schema.json

public-check:
	bash scripts/check_public_ready.sh

validate-demo:
	bash scripts/run_smoke_test.sh >/dev/null

install-skill:
	bash scripts/install_codex_skill.sh

package-check:
	set -e; \
	tmpdir="$$(mktemp -d)"; \
	python -m venv --system-site-packages "$$tmpdir/venv"; \
	PIP_NO_INDEX=1 PIP_CACHE_DIR="$$tmpdir/pip-cache" "$$tmpdir/venv/bin/python" -m pip install --no-build-isolation -e . >/dev/null; \
	"$$tmpdir/venv/bin/statebind" demo >/dev/null; \
	"$$tmpdir/venv/bin/statebind" --help >/dev/null
