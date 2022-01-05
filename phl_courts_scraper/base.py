"""Base class for downloading PDF and scraping data."""

import abc
import random
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from loguru import logger
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from tryagain import retries
from webdriver_manager.chrome import ChromeDriverManager
from webdriver_manager.firefox import GeckoDriverManager

from .utils import DataclassSchema, downloaded_pdf


def get_webdriver(
    browser: str, download_dir: Optional[str] = None, debug: bool = False
) -> Union[webdriver.Chrome, webdriver.Firefox]:
    """
    Initialize a selenium web driver with the specified options.

    Parameters
    ----------
    browser: str
        The browser to use; either 'chrome' or 'firefox'
    download_dir: str
        If specified, the name of the local download directory
    debug: bool
        Whether to use the headless version of Chrome

    Returns
    -------
    webdriver.Chrome, webdriver.Firefox
        The selenium web driver

    Raises
    ------
    ValueError
        If the browser is not 'chrome' or 'firefox'
    """
    # Google chrome
    if browser == "chrome":

        # Create the options
        options = webdriver.ChromeOptions()
        options.add_argument("--no-sandbox")
        if not debug:
            logger.info("Adding headless option")
            options.add_argument("--headless")

        # Set up the download directory for PDFs
        if download_dir is not None:
            profile = {
                "plugins.plugins_list": [
                    {"enabled": False, "name": "Chrome PDF Viewer"}
                ],  # Disable Chrome's PDF Viewer
                "download.default_directory": download_dir,
                "download.extensions_to_open": "applications/pdf",
            }
            options.add_experimental_option("prefs", profile)

        service = Service(ChromeDriverManager().install())
        logger.info("Chrome service initialized")
        logger.info("options = {}".format(options))
        driver = webdriver.Chrome(service=service, options=options)
        logger.info("Chrome driver initialized")

    # Firefox
    elif browser == "firefox":

        # Create the options
        options = webdriver.FirefoxOptions()
        if not debug:
            options.add_argument("--headless")

        service = Service(GeckoDriverManager().install())
        driver = webdriver.Firefox(service=service, options=options)
    else:
        raise ValueError(
            "Unknown browser type, should be 'chrome' or 'firefox'"
        )

    return driver


@dataclass  # type: ignore
class DownloadedPDFScraper(abc.ABC):
    """
    A base class to download and parse a PDF.

    Parameters
    ----------
    debug: bool
        Whether to use the headless version of Chrome
    log_freq: int, optional
        How often to log progress
    min_sleep: float, optional
        Minimum sleep time
    max_sleep: float, optional
        Maximum sleep time
    sleep: float, optional
        Sleep time between calls
    errors: str, optional
        How to handle scraping errors
    """

    debug: bool = False
    log_freq: int = 50
    min_sleep: int = 30
    max_sleep: int = 120
    sleep: int = 2
    errors: str = "ignore"

    def _init(self, dirname: str) -> None:
        """Initialize the web driver."""
        self.driver = get_webdriver(
            "chrome", download_dir=dirname, debug=self.debug
        )

    @abc.abstractmethod
    def __call__(self, pdf_path: Path, **kwargs: Any) -> DataclassSchema:
        """Scrape the PDF."""
        pass

    def scrape_remote_urls(
        self, urls: List[str], interval: int = 1, time_limit: int = 7
    ) -> List[Dict[str, str]]:
        """
        Download and scrape remote PDFs.

        Parameters
        ----------
        urls: List[str]
            The list of URLs to scrape
        interval: int
            How often to sleep between calls
        time_limit: int
            The maximum time to wait for the PDF to download

        Returns
        -------
        List[Dict[str, str]]

        Raises
        ------
        Exception
            If the PDF download fails
        """
        with tempfile.TemporaryDirectory() as tmpdir:

            # Initialize if we need to
            if not hasattr(self, "driver"):
                self._init(tmpdir)

            # Log the number
            N = len(urls)
            logger.info(f"Scraping info for {N} PDFs")

            # Save new results here
            results: List[Dict[str, str]] = []

            def cleanup() -> None:
                """Clean up the web driver."""
                self.driver.close()
                logger.info("Retrying...")

            @retries(
                max_attempts=10,
                cleanup_hook=cleanup,
                pre_retry_hook=lambda: self._init(tmpdir),
                wait=lambda n: min(
                    self.min_sleep + 2 ** n + random.random(), self.max_sleep
                ),
            )
            def call(i: int) -> None:
                """Call the scraper."""
                # Remote PDF paths
                remote_pdf_path = urls[i]

                # Log some info to screen?
                if i % self.log_freq == 0:
                    logger.debug(f"Done {i}")
                    logger.debug(f"Downloading PDF from '{remote_pdf_path}'")

                # Download the PDF
                with downloaded_pdf(
                    self.driver,
                    remote_pdf_path,
                    tmpdir,
                    interval=interval,
                    time_limit=time_limit,
                ) as pdf_path:

                    # Parse the report
                    report = self(pdf_path)

                    # Save the results
                    results.append(report.to_dict())

                # Sleep
                time.sleep(self.sleep)

            # Loop over shootings and scrape
            try:
                for i in range(N):
                    call(i)
            except Exception as e:
                # Skip
                if self.errors == "ignore":
                    logger.info(
                        f"Exception raised for i = {i} & PDF '{urls[i]}'"
                    )
                    logger.info(f"Ignoring exception: {str(e)}")

                # Raise
                else:
                    logger.exception(
                        f"Exception raised for i = {i} & PDF '{urls[i]}'"
                    )
                    raise
            finally:
                logger.debug(f"Done scraping: {i+1} PDFs scraped")

            return results
