.PHONY: install test scan dashboard

install:
	python -m pip install --upgrade pip
	pip install -e '.[dashboard,test]'

test:
	pytest

scan:
	veikkaus-monitor scan

dashboard:
	streamlit run app.py
