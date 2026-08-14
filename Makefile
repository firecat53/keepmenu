VENV = .venv
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

version:
	@grep -Po '^__version__ = "\K[^"]+' keepmenu/__init__.py

# Bump __version__, refresh the man page footer/date, commit, and create an
# annotated tag. The tag body becomes the GitHub release notes, so this opens
# $EDITOR for you to write them.
# Usage: make release VERSION=1.5.2
release:
	@test -n "$(VERSION)" || { echo "Usage: make release VERSION=x.y.z"; exit 1; }
	@echo "$(VERSION)" | grep -Pq '^\d+\.\d+\.\d+$$' || \
		{ echo "VERSION must be x.y.z"; exit 1; }
	@command -v pandoc >/dev/null || \
		{ echo "pandoc is required to regenerate the man page"; exit 1; }
	@test -z "$$(git status --porcelain -uno)" || \
		{ echo "Tracked files have uncommitted changes; commit or stash first"; exit 1; }
	@git rev-parse -q --verify refs/tags/$(VERSION) >/dev/null && \
		{ echo "Tag $(VERSION) already exists"; exit 1; } || true
	sed -i 's/^__version__ = ".*"$$/__version__ = "$(VERSION)"/' keepmenu/__init__.py
	sed -i -e 's/^footer: Keepmenu .*/footer: Keepmenu $(VERSION)/' \
		-e "s/^date: .*/date: $$(date '+%d %B %Y')/" keepmenu.1.md
	$(MAKE) man
	@test "$$($(MAKE) -s version)" = "$(VERSION)" || \
		{ echo "Failed to set version"; exit 1; }
	git commit -m "Bump version to $(VERSION)" \
		keepmenu/__init__.py keepmenu.1.md keepmenu.1
	# Prefill the subject with the version. CI builds the release notes
	# from the tag *body*, so anything on the first line would be dropped.
	git tag -a -e -m "$(VERSION)" $(VERSION)
	@echo
	@echo "Tagged $(VERSION). Push with:"
	@echo "    git push origin $$(git rev-parse --abbrev-ref HEAD) --follow-tags"

.PHONY: all venv run clean test man version release
