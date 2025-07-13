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


class LikeProcessor:
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
        await self._process_likes(action_config, processed_action_keys)

    async def _process_likes(
        self, action_config: ActionConfig, processed_action_keys: set
    ):
        if not action_config.enable_liking_tweets:
            return

        keywords_to_like = action_config.like_tweets_from_keywords or []
        if not keywords_to_like:
            logger.info(
                f"[{self.account.account_id}] Liking tweets enabled, but no keywords specified."
            )
            return

        logger.info(
            f"[{self.account.account_id}] Starting to like tweets based on {len(keywords_to_like)} keywords."
        )
        likes_done_this_run = 0
        for keyword in keywords_to_like:
            if likes_done_this_run >= action_config.max_likes_per_run:
                break

            tweets_to_potentially_like = await asyncio.to_thread(
                self.scraper.scrape_tweets_by_keyword,
                keyword,
                max_tweets=action_config.max_likes_per_run * 2,
            )

            for tweet_to_like in tweets_to_potentially_like:
                if likes_done_this_run >= action_config.max_likes_per_run:
                    break

                action_key = f"like_{self.account.account_id}_{tweet_to_like.tweet_id}"
                if action_key in processed_action_keys:
                    continue

                if (
                    action_config.avoid_replying_to_own_tweets
                    and tweet_to_like.user_handle
                    and self.account.account_id.lower()
                    in tweet_to_like.user_handle.lower()
                ):
                    continue

                like_success = await self.engagement.like_tweet(
                    tweet_id=tweet_to_like.tweet_id,
                    tweet_url=str(tweet_to_like.tweet_url)
                    if tweet_to_like.tweet_url
                    else None,
                )

                if like_success:
                    self.file_handler.save_processed_action_key(
                        action_key, timestamp=datetime.now().isoformat()
                    )
                    processed_action_keys.add(action_key)
                    likes_done_this_run += 1
                    await asyncio.sleep(
                        random.uniform(
                            action_config.min_delay_between_actions_seconds,
                            action_config.max_delay_between_actions_seconds,
                        )
                    )
