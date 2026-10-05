.PHONY: test clean

PY ?= python3

test:
	$(PY) -m unittest discover -s tests -v

clean:
	rm -rf __pycache__ tests/__pycache__ homework-archive/scripts/__pycache__
