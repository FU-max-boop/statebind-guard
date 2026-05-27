.PHONY: smoke test benchmark public-check install-skill

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

public-check:
	bash scripts/check_public_ready.sh

install-skill:
	bash scripts/install_codex_skill.sh
