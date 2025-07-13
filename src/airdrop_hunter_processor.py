
import asyncio
import random

from data_models import AccountConfig, ActionConfig, ScrapedTweet
from features.analyzer import TweetAnalyzer
from features.engagement import TweetEngagement
from features.publisher import TweetPublisher
from features.scraper import TweetScraper
from utils.file_handler import FileHandler
from utils.logger import setup_logger
from core.llm_service import LLMService

# Initialize logger
logger = setup_logger()


class AirdropHunterProcessor:
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

    async def process(self, action_config: ActionConfig, processed_action_keys: set):
        if not action_config.enable_airdrop_hunter:
            logger.info(f"[{self.account.account_id}] Airdrop Hunter is disabled for this account.")
            return

        logger.info(f"[{self.account.account_id}] Starting Airdrop Hunter process...")

        for keyword in action_config.airdrop_hunter_keywords:
            logger.info(f"[{self.account.account_id}] Searching for airdrops with keyword: {keyword}")
            
            # Scrape tweets
            tweets = await asyncio.to_thread(
                self.scraper.scrape_tweets_by_keyword,
                keyword,
                max_tweets=action_config.max_airdrop_tweets_per_run * 2,
            )

            for tweet in tweets:
                action_key = f"airdrop_{self.account.account_id}_{tweet.tweet_id}"
                if action_key in processed_action_keys:
                    logger.info(f"[{self.account.account_id}] Tweet {tweet.tweet_id} already processed for airdrop. Skipping.")
                    continue

                # Analyze tweet with LLM
                is_airdrop = await self.analyzer.is_airdrop_tweet(tweet)
                if not is_airdrop:
                    logger.info(f"[{self.account.account_id}] Tweet {tweet.tweet_id} is not an airdrop tweet. Skipping.")
                    continue

                logger.info(f"[{self.account.account_id}] Found potential airdrop tweet: {tweet.tweet_url}")

                # Perform actions
                await self._perform_airdrop_actions(tweet, action_config)

                processed_action_keys.add(action_key)
                self.file_handler.save_processed_action_key(action_key)

                await asyncio.sleep(
                    random.uniform(
                        action_config.min_delay_between_actions_seconds,
                        action_config.max_delay_between_actions_seconds,
                    )
                )

    async def _perform_airdrop_actions(self, tweet: ScrapedTweet, action_config: ActionConfig):
        # 1. Like the tweet
        await self.engagement.like_tweet(tweet.tweet_id, str(tweet.tweet_url))

        # 2. Retweet
        await self.publisher.retweet_tweet(tweet)

        # 3. Comment with address
        comment = None
        tweet_text_lower = tweet.text_content.lower()

        if "solana" in tweet_text_lower or "sol" in tweet_text_lower:
            if action_config.solana_address:
                comment = f"My Solana address: {action_config.solana_address}"
        elif "ethereum" in tweet_text_lower or "eth" in tweet_text_lower:
            if action_config.ethereum_address:
                comment = f"My Ethereum address: {action_config.ethereum_address}"
        elif "bitcoin" in tweet_text_lower or "btc" in tweet_text_lower:
            if action_config.bitcoin_address:
                comment = f"My Bitcoin address: {action_config.bitcoin_address}"

        if comment:
            await self.publisher.reply_to_tweet(tweet, comment)
            logger.info(f"[{self.account.account_id}] Commented with address on tweet {tweet.tweet_id}")
        else:
            logger.info(f"[{self.account.account_id}] No relevant address found in config for tweet {tweet.tweet_id}")

        # 4. Follow the user
        if tweet.user_handle:
            await self.engagement.follow_user(tweet.user_handle)
            logger.info(f"[{self.account.account_id}] Followed user {tweet.user_handle}")
