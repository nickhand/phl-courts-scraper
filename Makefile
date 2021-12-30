mypy:
	poetry run mypy phl_courts_scraper/ --config-file setup.cfg
flake8:
	poetry run flake8 --config setup.cfg
