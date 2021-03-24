import re
from pathlib import Path

from setuptools import find_packages, setup

PACKAGE_NAME = "phl_courts_scraper"
HERE = Path(__file__).parent.absolute()


def find_version(*paths: str) -> str:
    with HERE.joinpath(*paths).open("tr") as fp:
        version_file = fp.read()
    version_match = re.search(
        r"^__version__ = ['\"]([^'\"]*)['\"]", version_file, re.M
    )
    if version_match:
        return version_match.group(1)
    raise RuntimeError("Unable to find version string.")


setup(
    name=PACKAGE_NAME,
    version=find_version(PACKAGE_NAME, "__init__.py"),
    author="Nick Hand",
    maintainer="Nick Hand",
    maintainer_email="nick.hand@phila.gov",
    packages=find_packages(),
    description="A Python utility to scrape docket sheets and court summaries for Philadelphia courts",
    license="MIT",
    python_requires=">=3.6",
    install_requires=[
        "numpy",
        "pandas",
        "selenium",
        "webdriver_manager",
        "intervaltree",
        "pdfplumber",
        "desert",
        "tryagain",
    ],
)
