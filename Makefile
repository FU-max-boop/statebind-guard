.PHONY: smoke test benchmark adoption-context-evidence adoption-feedback-requests schema-check validate-demo public-check install-skill package-check dist-check

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
	python scripts/run_statebind_benchmark.py \
		--data data/statebind_guard_failure_corpus.json \
		--card docs/result_cards/statebind_guard_failure_corpus.md \
		--json docs/result_cards/statebind_guard_failure_corpus_metrics.json \
		--title "Failure Corpus"
	python scripts/run_statebind_benchmark.py \
		--data data/statebind_guard_deployed_corpus.json \
		--card docs/result_cards/statebind_guard_deployed_corpus.md \
		--json docs/result_cards/statebind_guard_deployed_corpus_metrics.json \
		--title "Deployed Corpus"

adoption-feedback-requests:
	python scripts/render_adoption_feedback_requests.py

adoption-context-evidence:
	python scripts/render_adoption_context_evidence.py

schema-check:
	python statebind_handoff/statebind_handoff.py schema --out /tmp/statebind.schema.json >/dev/null
	diff -u schemas/statebind.schema.json /tmp/statebind.schema.json
	python statebind_handoff/statebind_handoff.py schema --policy --out /tmp/statebind-policy.schema.json >/dev/null
	diff -u schemas/statebind-policy.schema.json /tmp/statebind-policy.schema.json

public-check:
	bash scripts/check_public_ready.sh

validate-demo:
	bash scripts/run_smoke_test.sh >/dev/null

install-skill:
	bash scripts/install_codex_skill.sh

package-check:
	set -e; \
	tmpdir="$$(mktemp -d)"; \
	PIP_CACHE_DIR="$$tmpdir/pip-cache" python -m pip wheel --no-deps --no-build-isolation -w "$$tmpdir/dist" . >/dev/null; \
	python -m venv "$$tmpdir/venv"; \
	PIP_NO_INDEX=1 PIP_FIND_LINKS="$$tmpdir/dist" PIP_CACHE_DIR="$$tmpdir/pip-cache" "$$tmpdir/venv/bin/python" -m pip install statebind-guard >/dev/null; \
	"$$tmpdir/venv/bin/python" -c 'import importlib.metadata; print(importlib.metadata.version("statebind-guard"))' >/dev/null; \
	"$$tmpdir/venv/bin/statebind" demo >/dev/null; \
	"$$tmpdir/venv/bin/statebind" proof >/dev/null; \
	"$$tmpdir/venv/bin/statebind" proof --json >/dev/null; \
	"$$tmpdir/venv/bin/statebind" --version >/dev/null; \
	"$$tmpdir/venv/bin/statebind" --help >/dev/null; \
	cd "$$tmpdir"; \
	git init -q; \
	"$$tmpdir/venv/bin/statebind" init --goal "package smoke" --next-command "make test" >/dev/null; \
	"$$tmpdir/venv/bin/statebind" policy --out .statebind-policy.json >/dev/null; \
	"$$tmpdir/venv/bin/statebind" install-hook --repo . --json statebind.json --policy .statebind-policy.json >/dev/null; \
	test -x .git/hooks/pre-commit; \
	"$$tmpdir/venv/bin/statebind" validate statebind.json --repo . --fail-on warning --policy .statebind-policy.json --summary statebind-summary.md --html-report statebind-report.html >/dev/null; \
	test -s statebind-summary.md; \
	test -s statebind-report.html; \
	"$$tmpdir/venv/bin/statebind" doctor --repo . >/dev/null

dist-check:
	set -e; \
	tmpdir="$$(mktemp -d)"; \
	version="$$(python -c 'import re; print(re.search(r"version = \"([^\"]+)\"", open("pyproject.toml", encoding="utf-8").read()).group(1))')"; \
	python scripts/build_dist.py --out "$$tmpdir/dist" >/dev/null; \
	test "$$(find "$$tmpdir/dist" -maxdepth 1 -name '*.whl' | wc -l | tr -d ' ')" = "1"; \
	test "$$(find "$$tmpdir/dist" -maxdepth 1 -name '*.tar.gz' | wc -l | tr -d ' ')" = "1"; \
	wheel="$$(find "$$tmpdir/dist" -maxdepth 1 -name '*.whl' -print -quit)"; \
	sdist="$$(find "$$tmpdir/dist" -maxdepth 1 -name '*.tar.gz' -print -quit)"; \
	case "$$wheel" in *"$$version"*) ;; *) echo "Wheel version mismatch: $$wheel" >&2; exit 1 ;; esac; \
	case "$$sdist" in *"$$version"*) ;; *) echo "Sdist version mismatch: $$sdist" >&2; exit 1 ;; esac; \
	tar -tf "$$sdist" | grep -q '/statebind_handoff/statebind_handoff.py'; \
	tar -tf "$$sdist" | grep -q '/README.md'; \
	tar -tf "$$sdist" | grep -q '/action.yml'; \
	tar -tf "$$sdist" | grep -q '/schemas/statebind.schema.json'; \
	PIP_CACHE_DIR="$$tmpdir/pip-cache" python -m pip wheel --no-deps --no-build-isolation -w "$$tmpdir/sdist-wheel" "$$sdist" >/dev/null; \
	python -m venv "$$tmpdir/venv"; \
	PIP_NO_INDEX=1 PIP_FIND_LINKS="$$tmpdir/dist" PIP_CACHE_DIR="$$tmpdir/pip-cache" "$$tmpdir/venv/bin/python" -m pip install statebind-guard >/dev/null; \
	"$$tmpdir/venv/bin/statebind" --version | grep -q "$$version"; \
	"$$tmpdir/venv/bin/statebind" proof >/dev/null; \
	cd "$$tmpdir"; \
	git init -q; \
	"$$tmpdir/venv/bin/statebind" init --goal "release artifact smoke" --next-command "make test" >/dev/null; \
	"$$tmpdir/venv/bin/statebind" policy --preset minimal --out .statebind-policy.json >/dev/null; \
	"$$tmpdir/venv/bin/statebind" validate statebind.json --repo . --policy .statebind-policy.json --fail-on warning --report statebind-validation.json --summary statebind-summary.md --html-report statebind-report.html >/dev/null; \
	test -s statebind-validation.json; \
	test -s statebind-summary.md; \
	test -s statebind-report.html; \
	"$$tmpdir/venv/bin/statebind" doctor --repo . --policy .statebind-policy.json >/dev/null
