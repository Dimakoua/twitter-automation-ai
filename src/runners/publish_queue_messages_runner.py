import asyncio
import os
import sys

# Add your project's root directory to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.browser_manager import BrowserManager
from core.config_loader import ConfigLoader
from core.llm_service import LLMService
from core.proxy_manager import ProxyManager
from data_models import (
    AccountConfig,
    TweetContent,
)
from features.publisher import TweetPublisher
from utils import FileMessageQueue
from utils.logger import setup_logger

# Initialize main config loader and logger
main_config_loader = ConfigLoader()
logger = setup_logger(main_config_loader)


async def get_publisher_for_account(
    account_id: str, config_loader: ConfigLoader, accounts_data: list
):
    """
    Retrieves or initializes a TweetPublisher for a given account ID.
    Caches publishers to reuse browser instances during a single script run.
    """

    found_account = None
    for account_dict in accounts_data:
        account = AccountConfig.model_validate(account_dict)
        if account.account_id == account_id:
            found_account = account_dict
            break

    if not found_account:
        logger.error(
            f"Account with ID '{account_id}' not found in accounts config. Cannot create publisher."
        )
        return None

    account_config = AccountConfig.model_validate(found_account)
    proxy_manager = ProxyManager(config_loader=config_loader)
    browser_manager = BrowserManager(
        account_config=found_account, proxy_manager=proxy_manager
    )
    llm_service = LLMService(config_loader=config_loader)

    publisher = TweetPublisher(browser_manager, llm_service, account_config)
    return publisher


async def run():
    config_loader = ConfigLoader()
    global_settings = config_loader.get_settings()
    accounts_data = config_loader.get_accounts_config()

    message_source_to_account_map = global_settings.get("twitter_automation", {}).get(
        "message_source_to_account_map", {}
    )
    if not message_source_to_account_map:
        logger.error(
            "No 'message_source_to_account_map' configured in global settings. Cannot process messages."
        )
        return

    queue = FileMessageQueue(queue_dir="twitter_queue")

    processed_messages_count = 0

    message, message_id = queue.get(block=False, poll_interval=1)

    if message is None:
        # No more messages in the queue
        if processed_messages_count == 0:
            logger.info("No new messages found in queue to process. Exiting.")
        else:
            logger.info(
                f"Finished processing {processed_messages_count} messages from queue."
            )
        return

    message_type = message.get("type")
    message_source = message.get("source")
    tweet_text = message.get("text")

    if (
        message_type != "generic_message_to_publish"
        or not tweet_text
        or not message_source
    ):
        logger.warning(
            f"Skipping malformed or irrelevant message. Type: {message_type}, Source: {message_source}, Text: {tweet_text[:50] if tweet_text else 'N/A'}"
        )
        queue.nack(message_id)
        return

    target_account_id = message_source_to_account_map.get(message_source)

    if not target_account_id:
        logger.error(
            f"No target account configured for message source '{message_source}'. Message will not be posted."
        )
        queue.nack(message_id)
        return

    publisher = await get_publisher_for_account(
        target_account_id, config_loader, accounts_data
    )
    if not publisher:
        logger.error(
            f"Could not get publisher for account '{target_account_id}'. Skipping message from source '{message_source}'."
        )
        queue.nack(message_id)
        return

    final_tweet_content = TweetContent(text=tweet_text)

    logger.info(
        f"Attempting to post message from source '{message_source}' to account '{target_account_id}'. Content preview: {final_tweet_content.text[:100]}..."
    )

    post_success = False
    try:
        post_success = await publisher.post_new_tweet(
            final_tweet_content, llm_settings=None
        )
    except Exception as e:
        logger.error(
            f"Error during tweet posting for source '{message_source}': {e}",
            exc_info=True,
        )
        queue.nack(message_id)

    if post_success:
        logger.info(
            f"Successfully posted message from source: {message_source} to account: {target_account_id}."
        )
        processed_messages_count += 1
        queue.ack(message_id)
    else:
        logger.error(
            f"Failed to post message from source: {message_source} to account: {target_account_id}. A debug snapshot may have been saved in media_files/logs."
        )
        queue.nack(message_id)

    publisher.browser_manager.close_driver()
    logger.info("Browser manager closed.")


if __name__ == "__main__":
    try:
        asyncio.run(run())
    except Exception as e:
        logger.critical(f"failed with critical error: {e}", exc_info=True)
    finally:
        logger.info("shutdown complete.")
