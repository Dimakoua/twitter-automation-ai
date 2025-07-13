import os
import sys
import time
from typing import Optional

from selenium.common.exceptions import (
    ElementClickInterceptedException,
    NoSuchElementException,
    TimeoutException,
)
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webelement import WebElement  # Import WebElement
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

# Adjust import paths
try:
    from ..core.browser_manager import BrowserManager
    from ..core.config_loader import ConfigLoader
    from ..data_models import AccountConfig, ScrapedTweet
    from ..utils.logger import setup_logger
except ImportError:
    sys.path.append(
        os.path.join(os.path.dirname(__file__), "..", "..")
    )  # Add root src to path
    from src.core.browser_manager import BrowserManager
    from src.core.config_loader import ConfigLoader
    from src.data_models import AccountConfig, ScrapedTweet
    from src.utils.logger import setup_logger

config_loader_instance = ConfigLoader()
logger = setup_logger(config_loader_instance)


class TweetEngagement:
    def __init__(self, browser_manager: BrowserManager, account_config: AccountConfig):
        self.browser_manager = browser_manager
        self.driver = self.browser_manager.get_driver()
        self.account_config = account_config
        self.config_loader = browser_manager.config_loader

    def _force_click(self, element: WebElement):
        """Attempts a standard click, falls back to a JavaScript click if intercepted."""
        try:
            element.click()
        except ElementClickInterceptedException:
            logger.warning(
                f"Click intercepted for element: {element.tag_name}. Forcing click with JavaScript."
            )
            self.driver.execute_script("arguments[0].click();", element)

    def _find_tweet_on_page(self, tweet_id: str) -> Optional[WebElement]:
        """
        Attempts to find a tweet article element by its ID within its URL.
        This is a helper and might need to be more robust if tweets are not directly addressable
        or if the current page doesn't show the tweet directly.
        """
        try:
            # Construct an XPath to find an article that contains a link with the tweet ID.
            # This assumes the tweet is visible on the current page.
            xpath_selector = f"//article[.//a[contains(@href, '/status/{tweet_id}')]]"
            tweet_element = self.driver.find_element(By.XPATH, xpath_selector)
            logger.info(f"Found tweet element for ID {tweet_id} on page.")
            return tweet_element
        except NoSuchElementException:
            logger.warning(
                f"Tweet element with ID {tweet_id} not found on the current page."
            )
            return None

    async def like_tweet(self, tweet_id: str, tweet_url: Optional[str] = None) -> bool:
        """
        Likes a tweet given its ID. Navigates to the tweet URL if provided and necessary.
        """
        logger.info(f"Attempting to like tweet ID: {tweet_id}")

        original_url = None
        tweet_card_element = None

        try:
            # If a tweet URL is provided, navigate to it first.
            if tweet_url:
                original_url = self.driver.current_url
                if (
                    not tweet_id in original_url
                ):  # Only navigate if not already on a page related to the tweet
                    logger.info(f"Navigating to tweet URL: {tweet_url}")
                    self.browser_manager.navigate_to(tweet_url)
                    time.sleep(3)  # Wait for page to load

            # Attempt to find the specific tweet card on the page
            # This is crucial if liking from a feed or search results.
            # If already on the tweet's direct page, the like button might be easier to find.
            tweet_card_element = self._find_tweet_on_page(tweet_id)

            if not tweet_card_element:
                # If not found on current page (e.g. after navigation or if not on direct URL)
                # and no URL was given to navigate to, we can't proceed.
                if not tweet_url:
                    logger.error(
                        f"Cannot like tweet {tweet_id}: Not found on page and no URL provided."
                    )
                    return False
                # If URL was provided but still not found, it's an issue.
                logger.error(
                    f"Tweet {tweet_id} not found even after navigating to {tweet_url}."
                )
                return False

            already_liked_xpath = './/button[@data-testid="unlike"]'

            try:
                # If "unlike" button exists, it's already liked
                tweet_card_element.find_element(By.XPATH, already_liked_xpath)
                logger.info(
                    f"Tweet {tweet_id} is already liked (data-testid indicates unlike)."
                )
                return True
            except NoSuchElementException:
                # Otherwise, click the "like" button
                like_button_xpath = './/button[@data-testid="like"]'
                like_button = WebDriverWait(tweet_card_element, 10).until(
                    EC.element_to_be_clickable((By.XPATH, like_button_xpath))
                )
            self._force_click(like_button)
            logger.info(f"Clicked like button for tweet {tweet_id}.")

            # Optionally, wait for a visual confirmation (e.g., button state change)
            time.sleep(60)  # Brief pause for action to register

            # Verify if liked (e.g., check aria-label again)
            # Re-fetch the button as its state might have changed its properties
            try:
                tweet_card_element.find_element(By.XPATH, already_liked_xpath)
                logger.info(f"Successfully liked tweet {tweet_id}.")
                return True
            except NoSuchElementException:
                logger.warning(
                    f"Failed to confirm like for tweet {tweet_id} (aria-label did not change to 'Unlike')."
                )
                return False

        except TimeoutException:
            logger.error(f"Timeout while trying to like tweet {tweet_id}.")
            return False
        except ElementClickInterceptedException:
            logger.error(
                f"Like button click intercepted for tweet {tweet_id}. Possible overlay or popup."
            )
            # Try to close overlays or scroll, then retry - advanced handling
            return False
        except Exception as e:
            logger.error(f"Failed to like tweet {tweet_id}: {e}", exc_info=True)
            return False
        finally:
            # Optionally navigate back if we moved from a different page
            # if tweet_url and original_url and original_url != self.driver.current_url:
            #     logger.info(f"Navigating back to original URL: {original_url}")
            #     self.driver.get(original_url)
            #     time.sleep(2)
            pass  # No specific navigation back logic by default, handled by orchestrator if needed.
