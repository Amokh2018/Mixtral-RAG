.PHONY: init install run

init:
	python3 -m venv venv
	. venv/bin/activate && pip install --upgrade pip && pip install -r requirements.txt

install:
	pip install --upgrade pip && pip install -r requirements.txt

run:
	. venv/bin/activate && python app.py
