PREFIX ?= /usr
DESTDIR ?=
BINDIR = $(PREFIX)/bin
DATADIR = $(PREFIX)/share
PYTHON ?= python3

.PHONY: install uninstall

install:
	# Install Python package
	$(PYTHON) -m pip install --root="$(DESTDIR)/" --prefix="$(PREFIX)" --no-deps .
	# Desktop entry
	install -Dm644 anvil-organizer.desktop \
		"$(DESTDIR)$(DATADIR)/applications/anvil-organizer.desktop"
	# Icons
	install -Dm644 anvil/resources/logo.png \
		"$(DESTDIR)$(DATADIR)/icons/hicolor/256x256/apps/anvil-organizer.png"
	install -Dm644 anvil/resources/logo.svg \
		"$(DESTDIR)$(DATADIR)/icons/hicolor/scalable/apps/anvil-organizer.svg"

uninstall:
	$(PYTHON) -m pip uninstall -y anvil-organizer
	rm -f "$(DESTDIR)$(DATADIR)/applications/anvil-organizer.desktop"
	rm -f "$(DESTDIR)$(DATADIR)/icons/hicolor/256x256/apps/anvil-organizer.png"
	rm -f "$(DESTDIR)$(DATADIR)/icons/hicolor/scalable/apps/anvil-organizer.svg"
