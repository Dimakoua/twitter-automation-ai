import asyncio
import random
from datetime import datetime

from core.config_loader import ConfigLoader
from core.llm_service import LLMService
from data_models import AccountConfig, ActionConfig
from features.analyzer import TweetAnalyzer
from features.engagement import TweetEngagement
from features.publisher import TweetPublisher
from features.scraper import TweetScraper
from utils.file_handler import FileHandler
from utils.logger import setup_logger

config_loader_instance = ConfigLoader()
logger = setup_logger(config_loader_instance)


class CommentProcessor:
    def __init__(
        self,
        scraper: TweetScraper,
        publisher: TweetPublisher,
        engagement: TweetEngagement,
        analyzer: TweetAnalyzer,
        llm_service: LLMService,
        account: AccountConfig,
        file_handler: FileHandler,
    ):
        self.scraper = scraper
        self.publisher = publisher
        self.engagement = engagement
        self.analyzer = analyzer
        self.llm_service = llm_service
        self.account = account
        self.file_handler = file_handler

    async def process(
        self,
        action_config: ActionConfig,
        processed_action_keys: set,
    ):
        await self._process_comments(action_config, processed_action_keys)

    async def _process_comments(
        self, action_config: ActionConfig, processed_action_keys: set
    ):
        if not action_config.enable_keyword_replies:
            return

        target_keywords = self.account.target_keywords
        if not target_keywords:
            logger.info(
                f"[{self.account.account_id}] Keyword replies enabled, but no target keywords configured for this account."
            )
            return

        logger.info(
            f"[{self.account.account_id}] Starting keyword scraping and replying for {len(target_keywords)} keywords."
        )
        for keyword in target_keywords:
            tweets_for_keyword = await asyncio.to_thread(
                self.scraper.scrape_tweets_by_keyword,
                keyword,
                max_tweets=action_config.max_replies_per_keyword_run * 2,
            )

            replies_made_this_keyword = 0
            for scraped_tweet_to_reply in tweets_for_keyword:
                if (
                    replies_made_this_keyword
                    >= action_config.max_replies_per_keyword_run
                ):
                    break

                action_key = (
                    f"reply_{self.account.account_id}_{scraped_tweet_to_reply.tweet_id}"
                )
                if action_key in processed_action_keys:
                    continue

                if (
                    action_config.avoid_replying_to_own_tweets
                    and scraped_tweet_to_reply.user_handle
                    and self.account.account_id.lower()
                    in scraped_tweet_to_reply.user_handle.lower()
                ):
                    continue

                llm_for_reply = (
                    self.account.llm_settings_override
                    or action_config.llm_settings_for_reply
                )

                reply_prompt = f"""
                    Generate a concise, original, and engaging reply to the tweet below.

                    Original tweet by @{scraped_tweet_to_reply.user_handle or "user"}:  
                    "{scraped_tweet_to_reply.text_content}"

                    Instructions:
                    - Only reply if the tweet is about crypto, memecoins, or altcoins. Otherwise, return: FALSE
                    - Write like a savvy, plugged-in crypto trader. Keep it sharp and clean.
                    - Do NOT use any of the following:
                    * Clichés like "DYOR", "classic cycle", "to the moon", etc.
                    * Dashes (– or -)  
                    * Mentions or links (including usernames like @example)  
                    - If the tweet is about memecoins or low caps, you may subtly hint at smarter tools or sources that sharper traders use  
                    - Do not sound promotional. Be casual, confident, and a little cryptic  
                    - Reply should feel like a smart trader dropping a quick insight

                    Your reply:
                """
                generated_reply_text = await self.llm_service.generate_text(
                    prompt=reply_prompt,
                    service_preference=llm_for_reply.service_preference,
                    model_name=llm_for_reply.model_name_override,
                    max_tokens=llm_for_reply.max_tokens,
                    temperature=llm_for_reply.temperature,
                )

                if not generated_reply_text or "FALSE" in generated_reply_text:
                    continue

                reply_success = await self.publisher.reply_to_tweet(
                    scraped_tweet_to_reply, generated_reply_text
                )

                if reply_success:
                    self.file_handler.save_processed_action_key(
                        action_key, timestamp=datetime.now().isoformat()
                    )
                    processed_action_keys.add(action_key)
                    replies_made_this_keyword += 1
                    await asyncio.sleep(
                        random.uniform(
                            action_config.min_delay_between_actions_seconds,
                            action_config.max_delay_between_actions_seconds,
                        )
                    )
