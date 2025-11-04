.PHONY: all venv

PKG := uv
VENV_DIR := .venv
PYTHON := $(VENV_DIR)/bin/python
PIP := $(VENV_DIR)/bin/pip

image_downloader:
	$(PKG) run --env-file .env ./data/image_data.py

crime_pipeline:
	$(PKG) run --env-file .env ./data/crime_data.py

# Installs all project dependencies
install:
	$(PKG) sync 

# Deletes virtual environment
reset:
	rm -rf .venv
