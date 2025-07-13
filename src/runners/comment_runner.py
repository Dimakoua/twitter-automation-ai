import asyncio
import os
import sys

# Ensure src directory is in Python path for imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from core.browser_manager import BrowserManager
from core.config_loader import ConfigLoader
from core.llm_service import LLMService
from data_models import (
    AccountConfig,
    ActionConfig,
)
from features.analyzer import TweetAnalyzer
from features.engagement import TweetEngagement
from features.publisher import TweetPublisher
from features.scraper import TweetScraper
from processors.comments import CommentProcessor
from utils.file_handler import FileHandler
from utils.logger import setup_logger

# Initialize main config loader and logger
main_config_loader = ConfigLoader()
logger = setup_logger(main_config_loader)


class CommentRunner:
    def __init__(self):
        self.config_loader = main_config_loader
        self.file_handler = FileHandler(self.config_loader)
        self.global_settings = self.config_loader.get_settings()
        self.accounts_data = self.config_loader.get_accounts_config()

        self.processed_action_keys = (
            self.file_handler.load_processed_action_keys()
        )  # Load processed action keys

    async def _process_account(self, account_dict: dict):
        """Processes tasks for a single Twitter account."""

        try:
            account = AccountConfig.model_validate(account_dict)
        except Exception as e:
            logger.error(
                f"Failed to parse account configuration for {account_dict.get('account_id', 'UnknownAccount')}: {e}. Skipping account."
            )
            return

        if not account.is_active:
            logger.info(f"Account {account.account_id} is inactive. Skipping.")
            return

        logger.info(f"--- Starting processing for account: {account.account_id} ---")

        browser_manager = None
        try:
            browser_manager = BrowserManager(account_config=account_dict)
            llm_service = LLMService(config_loader=self.config_loader)

            scraper = TweetScraper(browser_manager, account_id=account.account_id)
            publisher = TweetPublisher(browser_manager, llm_service, account)
            engagement = TweetEngagement(browser_manager, account)
            analyzer = TweetAnalyzer(llm_service, account_config=account)

            automation_settings = self.global_settings.get("twitter_automation", {})
            global_action_config_dict = automation_settings.get("action_config", {})
            current_action_config = account.action_config or ActionConfig(
                **global_action_config_dict
            )

            like_and_comment_processor = CommentProcessor(
                scraper,
                publisher,
                engagement,
                analyzer,
                llm_service,
                account,
                self.file_handler,
            )
            await like_and_comment_processor.process(
                current_action_config, self.processed_action_keys
            )

            logger.info(
                f"[{account.account_id}] Finished processing tasks for this account."
            )

        except Exception as e:
            logger.error(
                f"[{account.account_id or 'UnknownAccount'}] Unhandled error during account processing: {e}",
                exc_info=True,
            )
        finally:
            if browser_manager:
                browser_manager.close_driver()
            account_id_for_log = account_dict.get("account_id", "UnknownAccount")
            if "account" in locals() and hasattr(account, "account_id"):
                account_id_for_log = account.account_id
            logger.info(
                f"--- Finished processing for account: {account_id_for_log} ---"
            )
            await asyncio.sleep(
                self.global_settings.get("delay_between_accounts_seconds", 10)
            )

    async def run(self):
        logger.info("Twitter Orchestrator starting...")
        if not self.accounts_data:
            logger.warning(
                "No accounts found in configuration. Orchestrator will exit."
            )
            return

        tasks = [
            self._process_account(account_dict) for account_dict in self.accounts_data
        ]
        logger.info(f"Starting concurrent processing for {len(tasks)} accounts.")
        results = await asyncio.gather(*tasks, return_exceptions=True)

        for i, result in enumerate(results):
            account_id = self.accounts_data[i].get("account_id", f"AccountIndex_{i}")
            if isinstance(result, Exception):
                logger.error(
                    f"Error processing account {account_id}: {result}", exc_info=result
                )
            else:
                logger.info(
                    f"Successfully completed processing for account {account_id}."
                )

        logger.info("Twitter Orchestrator finished processing all accounts.")


if __name__ == "__main__":
    orchestrator = CommentRunner()
    try:
        asyncio.run(orchestrator.run())
    except KeyboardInterrupt:
        logger.info("Orchestrator run interrupted by user.")
    except Exception as e:
        logger.critical(f"Orchestrator failed with critical error: {e}", exc_info=True)
    finally:
        logger.info("Orchestrator shutdown complete.")
