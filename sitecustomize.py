import os


# The virtualenv ships a pytest-pymtl3 plugin that is incompatible with the
# installed pytest version and crashes during collection. Disable third-party
# auto-loading so the repo tests can run deterministically.
os.environ.setdefault("PYTEST_DISABLE_PLUGIN_AUTOLOAD", "1")
