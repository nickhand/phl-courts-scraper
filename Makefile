mypy:
	poetry run mypy --config-file setup.cfg
flake8:
	poetry run flake8 --config setup.cfg
