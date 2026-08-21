PYTHON ?= python
PYTHONPATH := src

.PHONY: install demo bench perf test policy-check portability smt quality

install:
	$(PYTHON) -m pip install -e .

demo:
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) -m veritas demo

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

quality: test portability policy-check

