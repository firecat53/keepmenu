VENV = .venv
PYTHON = $(VENV)/bin/python
# Via the interpreter, so a venv whose console scripts are missing or
# non-executable still works.
PIP = $(PYTHON) -m pip

all: venv

$(VENV)/bin/activate: pyproject.toml
	python3 -m venv $(VENV)
	$(PIP) install -U pip wheel
	# Editable, to match flake.nix. A non-editable install silently
	# replaces the flake's editable one, and then `make test` tests a
	# snapshot of the tree rather than the tree.
	$(PIP) install -e '.[autotype]'

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
# annotated tag. $EDITOR prefilled with version and commits since the last tag.
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
	# Open the tag message prefilled with the version as the subject and one
	# bullet per commit since the last tag.
	@notes=$$(mktemp); \
	prev=$$(git describe --tags --abbrev=0 2>/dev/null); \
	{ echo "$(VERSION)"; echo; \
	  git log --no-merges --invert-grep \
		--grep='^Bump version to ' --format='* %s' \
		$${prev:+$$prev..}HEAD; } > $$notes; \
	git tag -a -e -F $$notes $(VERSION); status=$$?; \
	rm -f $$notes; \
	test $$status -eq 0 || exit $$status; \
	test -n "$$(git for-each-ref --format='%(contents:body)' \
		refs/tags/$(VERSION))" || { \
		git tag -d $(VERSION) >/dev/null; \
		echo "Tag message body is empty, so the release notes would be too."; \
		echo "Tag not created. The version bump commit is still there;"; \
		echo "undo it with: git reset --hard HEAD^"; \
		exit 1; }
	@echo
	@echo "Tagged $(VERSION). Push with:"
	@echo "    git push origin $$(git rev-parse --abbrev-ref HEAD) --follow-tags"

.PHONY: all venv run clean test man version release
