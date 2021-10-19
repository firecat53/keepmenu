VENV = venv
PYTHON = $(VENV)/bin/python
PIP = $(VENV)/bin/pip

all: venv

$(VENV)/bin/activate: requirements.txt
	python3 -m venv $(VENV)
	$(PIP) install -U pip wheel
	$(PIP) install .

venv: $(VENV)/bin/activate

run: venv
	$(VENV)/bin/keepmenu

clean:
	rm -rf __pycache__
	rm -rf $(VENV)

man: keepmenu.1.md
	pandoc keepmenu.1.md -s -t man -o keepmenu.1

test: venv
	$(PYTHON) tests/tests.py

.PHONY: all venv run clean
