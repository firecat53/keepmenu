# keepmenu
# See LICENSE file for copyright and license details.



install: keepmenu
	echo Installing requirements
	pip install $(cat requirements.txt)
	mkdir -p $(DESTDIR)$(PREFIX)/bin
	cp -f keepmenu $(DESTDIR)$(PREFIX)/bin
	chmod 755 $(DESTDIR)$(PREFIX)/bin/keepmenu

uninstall:
	rm -f $(DESTDIR)$(PREFIX)/bin/keepemenu
	pip uninstall $(cat requirements.txt)

