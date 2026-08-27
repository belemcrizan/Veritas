PYTHON ?= python
PYTHONPATH := src

.PHONY: install demo example bench perf test policy-check portability smt docs package quality showcase

install:
	$(PYTHON) -m pip install -e .

demo:
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) -m veritas demo

example:
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) examples/library_integration.py

bench:
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) -m veritas bench

perf:
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) -m veritas perf --iterations 1000

test:
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) -m unittest discover -s tests -v

policy-check:
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) -m veritas policy-check policies/payment_policy.json

portability:
	$(PYTHON) tools/check_portability.py

smt:
	$(PYTHON) tools/check_smt.py

docs:
	$(PYTHON) -m mkdocs build --strict

package:
	$(PYTHON) -m build
	$(PYTHON) -m twine check dist/*

quality: test example portability policy-check

showcase:
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) -m veritas showcase
