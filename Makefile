PY=python

dist/*.tar.gz:
	$(PY) -m build

install: dist/*.tar.gz
	$(PY) -m pip install dist/*.tar.gz

uninstall:
	$(PY) -m pip uninstall mockasite

.PHONY: clean

clean:
	rm -rf dist
