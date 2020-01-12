# keepmenu
# See LICENSE file for copyright and license details.


install: keepmenu
	echo Installing requirements
	sudo pip install pykeepass PyUserInput
	sudo mkdir -p $(DESTDIR)$(PREFIX)/bin
	sudo cp -f keepmenu $(DESTDIR)$(PREFIX)/bin
	sudo chmod 755 $(DESTDIR)$(PREFIX)/bin/keepmenu

uninstall:
	rm -f $(DESTDIR)$(PREFIX)/bin/keepemenu
	sudo pip uninstall $(cat requirements.txt)

