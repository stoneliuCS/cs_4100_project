.PHONY: all venv

PKG := uv
VENV_DIR := .venv
PYTHON := $(VENV_DIR)/bin/python
PIP := $(VENV_DIR)/bin/pip


run_graph_pipeline:
	PYTHONPATH=. $(PKG) run --env-file .env ./graph/main.py
run_data_pipeline:
	PYTHONPATH=. $(PKG) run --env-file .env ./data/main.py

# Installs all project dependencies
install:
	$(PKG) sync 

# Deletes virtual environment
reset:
	rm -rf .venv
