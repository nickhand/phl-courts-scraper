import random
import tempfile
import time
from dataclasses import dataclass

from loguru import logger
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from tryagain import retries
from webdriver_manager.chrome import ChromeDriverManager

from .utils import downloaded_pdf


def get_webdriver(browser, dirname, debug=False):
    """Get the webdriver."""

    if browser == "chrome":
        options = webdriver.ChromeOptions()
        options.add_argument("--no-sandbox")
        if not debug:
            options.add_argument("--headless")

        # Setup the download directory for PDFs
        profile = {
            "plugins.plugins_list": [
                {"enabled": False, "name": "Chrome PDF Viewer"}
            ],  # Disable Chrome's PDF Viewer
            "download.default_directory": dirname,
            "download.extensions_to_open": "applications/pdf",
        }
        options.add_experimental_option("prefs", profile)

        # Initialize with options
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)
    else:
        raise ValueError("Unknown browser type, should be 'chrome'")

    return driver


@dataclass
class DownloadedPDFScraper:
    """A class to download and parse a PDF."""

    browser: str = "chrome"
    debug: bool = False
    log_freq: int = 50
    min_sleep: int = 30
    max_sleep: int = 120
    sleep: int = 2
    errors: str = "ignore"

    def _init(self, dirname):
        """Initialization function."""

        # Get the driver
        self.driver = get_webdriver(self.browser, dirname, debug=self.debug)

    def scrape_remote_urls(self, urls, interval=1, time_limit=7):
        """Scrape remote PDFs."""

        with tempfile.TemporaryDirectory() as tmpdir:

            # Initialize if we need to
            if not hasattr(self, "driver"):
                self._init(tmpdir)

            # Log the number
            N = len(urls)
            logger.info(f"Scraping info for {N} PDFs")

            # Save new results here
            results = {}

            def cleanup():
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
            def _call(i):

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
                    results[remote_pdf_path] = report.to_dict()

                # Sleep
                time.sleep(self.sleep)

            # Loop over shootings and scrape
            try:
                for i in range(N):
                    _call(i)
            except Exception as e:
                # Skip
                if self.errors == "ignore":
                    logger.info(f"Exception raised for i = {i} & PDF '{urls[i]}'")
                    logger.info(f"Ignoring exception: {str(e)}")

                    # Add None for failure
                    results[urls[i]] = None

                # Raise
                else:
                    logger.exception(f"Exception raised for i = {i} & PDF '{urls[i]}'")
                    raise
            finally:
                logger.debug(f"Done scraping: {i+1} PDFs scraped")

            return results
