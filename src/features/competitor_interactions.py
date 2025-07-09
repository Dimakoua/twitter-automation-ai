import asyncio
import random
from datetime import datetime

from core.llm_service import LLMService
from data_models import AccountConfig, ActionConfig, TweetContent
from features.scraper import TweetScraper
from features.publisher import TweetPublisher
from features.analyzer import TweetAnalyzer
from utils.file_handler import FileHandler
from utils.logger import setup_logger
from core.config_loader import ConfigLoader

config_loader_instance = ConfigLoader()
logger = setup_logger(config_loader_instance)

class CompetitorProcessor:
    def __init__(
        self,
        scraper: TweetScraper,
        publisher: TweetPublisher,
        analyzer: TweetAnalyzer,
        llm_service: LLMService,
        account: AccountConfig,
        file_handler: FileHandler,
    ):
        self.scraper = scraper
        self.publisher = publisher
        self.analyzer = analyzer
        self.llm_service = llm_service
        self.account = account
        self.file_handler = file_handler

    async def process(
        self,
        action_config: ActionConfig,
        processed_action_keys: set,
    ):
        competitor_profiles = self.account.competitor_profiles
        if not action_config.enable_competitor_reposts or not competitor_profiles:
            if action_config.enable_competitor_reposts:
                logger.info(
                    f"[{self.account.account_id}] Competitor reposts enabled, but no competitor profiles configured for this account."
                )
            return

        logger.info(
            f"[{self.account.account_id}] Starting competitor profile scraping and posting using {len(competitor_profiles)} profiles."
        )
        for profile_url in competitor_profiles:
            logger.info(
                f"[{self.account.account_id}] Scraping profile: {str(profile_url)}"
            )

            tweets_from_profile = await asyncio.to_thread(
                self.scraper.scrape_tweets_from_profile,
                str(profile_url),
                max_tweets=action_config.max_posts_per_competitor_run * 3,
            )

            posts_made_this_profile = 0
            for scraped_tweet in tweets_from_profile:
                if (
                    posts_made_this_profile
                    >= action_config.max_posts_per_competitor_run
                ):
                    break

                if (
                    action_config.repost_only_tweets_with_media
                    and not scraped_tweet.embedded_media_urls
                ):
                    logger.debug(
                        f"[{self.account.account_id}] Skipping tweet {scraped_tweet.tweet_id} (no media)."
                    )
                    continue
                if (
                    scraped_tweet.like_count
                    < action_config.min_likes_for_repost_candidate
                ):
                    logger.debug(
                        f"[{self.account.account_id}] Skipping tweet {scraped_tweet.tweet_id} (likes {scraped_tweet.like_count} < min)."
                    )
                    continue
                if (
                    scraped_tweet.retweet_count
                    < action_config.min_retweets_for_repost_candidate
                ):
                    logger.debug(
                        f"[{self.account.account_id}] Skipping tweet {scraped_tweet.tweet_id} (retweets {scraped_tweet.retweet_count} < min)."
                    )
                    continue

                interaction_type = (
                    action_config.competitor_post_interaction_type
                )
                action_key = f"{interaction_type}_{self.account.account_id}_{scraped_tweet.tweet_id}"

                if action_key in processed_action_keys:
                    logger.info(
                        f"[{self.account.account_id}] Action '{action_key}' already processed. Skipping."
                    )
                    continue

                llm_for_reply = (
                    self.account.llm_settings_override
                    or action_config.llm_settings_for_reply
                )
                llm_for_post = (
                    self.account.llm_settings_override
                    or action_config.llm_settings_for_post
                )
                llm_for_thread_analysis = (
                    self.account.llm_settings_override
                    or action_config.llm_settings_for_thread_analysis
                )

                if (
                    scraped_tweet.is_thread_candidate
                    and action_config.enable_thread_analysis
                ):
                    is_confirmed = await self.analyzer.check_if_thread_with_llm(
                        scraped_tweet,
                        custom_llm_settings=llm_for_thread_analysis,
                    )
                    scraped_tweet.is_confirmed_thread = is_confirmed
                    logger.info(
                        f"[{self.account.account_id}] Thread analysis result for {scraped_tweet.tweet_id}: {is_confirmed}"
                    )

                interaction_success = False

                if interaction_type == "repost":
                    prompt = f"Rewrite this tweet in an engaging way: '{scraped_tweet.text_content}' by {scraped_tweet.user_handle or 'a user. Provide only one-two clean sentence. This is used by bot. Text must be ready to post on Twitter.'}."
                    if scraped_tweet.is_confirmed_thread:
                        prompt = f"This tweet is part of a thread. Rewrite its essence engagingly: '{scraped_tweet.text_content}' by {scraped_tweet.user_handle or 'a user. Provide only one-two clean sentence. This is used by bot. Text must be ready to post on Twitter.'}."

                    generated_text = await self.llm_service.generate_text(
                        prompt=prompt,
                        service_preference=llm_for_reply.service_preference,
                        model_name=llm_for_reply.model_name_override,
                        max_tokens=llm_for_reply.max_tokens,
                        temperature=llm_for_reply.temperature,
                    )

                    new_tweet_content = TweetContent(text=generated_text)
                    interaction_success = await self.publisher.post_new_tweet(
                        new_tweet_content, llm_settings=llm_for_post
                    )

                elif interaction_type == "retweet":
                    interaction_success = await self.publisher.retweet_tweet(
                        scraped_tweet
                    )

                elif interaction_type == "quote_tweet":
                    quote_prompt_templates = action_config.prompt_for_quote_tweet_from_competitor
                    quote_prompt_template = random.choice(
                        quote_prompt_templates
                    )
                    quote_prompt = quote_prompt_template.format(
                        user_handle=(scraped_tweet.user_handle or "a user"),
                        tweet_text=scraped_tweet.text_content,
                    )
                    interaction_success = await self.publisher.retweet_tweet(
                        scraped_tweet,
                        quote_text_prompt_or_direct=quote_prompt,
                        llm_settings_for_quote=llm_for_post,
                    )
                else:
                    logger.warning(
                        f"[{self.account.account_id}] Unknown competitor_post_interaction_type: {interaction_type}"
                    )
                    continue

                if interaction_success:
                    self.file_handler.save_processed_action_key(
                        action_key, timestamp=datetime.now().isoformat()
                    )
                    processed_action_keys.add(action_key)
                    posts_made_this_profile += 1
                    await asyncio.sleep(
                        random.uniform(
                            action_config.min_delay_between_actions_seconds,
                            action_config.max_delay_between_actions_seconds,
                        )
                    )
                else:
                    logger.error(
                        f"[{self.account.account_id}] Failed to {interaction_type} based on tweet {scraped_tweet.tweet_id}"
                    )