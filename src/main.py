import asyncio
import os
import random
import sys
import time
from datetime import datetime, timezone

# Ensure src directory is in Python path for imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from core.browser_manager import BrowserManager
from core.config_loader import ConfigLoader
from core.llm_service import LLMService
from data_models import (
    AccountConfig,
    ActionConfig,
    LLMSettings,
    ScrapedTweet,
    TweetContent,
)
from features.analyzer import TweetAnalyzer
from features.engagement import TweetEngagement
from features.publisher import TweetPublisher
from features.scraper import TweetScraper
from utils.file_handler import FileHandler
from utils.logger import setup_logger
from airdrop_hunter_processor import AirdropHunterProcessor

# Initialize main config loader and logger
main_config_loader = ConfigLoader()
logger = setup_logger(main_config_loader)


class TwitterOrchestrator:
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

        # Create AccountConfig Pydantic model from the dictionary
        try:
            # A simple way to map, assuming keys in dict match model fields or are handled by default values
            # account_config_data = {k: account_dict.get(k) for k in AccountConfig.model_fields.keys() if account_dict.get(k) is not None}
            # if 'cookies' in account_dict and isinstance(account_dict['cookies'], str): # If 'cookies' is a file path string
            #     account_config_data['cookie_file_path'] = account_dict['cookies']
            #     if 'cookies' in account_config_data: del account_config_data['cookies'] # Avoid conflict if model expects List[AccountCookie]

            # Use Pydantic's parse_obj method for robust parsing from dict
            account = AccountConfig.model_validate(account_dict)

        except Exception as e:  # Catch Pydantic ValidationError specifically if needed
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
            logger.debug(f"Loaded settings: {self.config_loader.get_settings()}")
            llm_service = LLMService(config_loader=self.config_loader)

            # Initialize feature modules with the current account's context
            scraper = TweetScraper(browser_manager, account_id=account.account_id)
            publisher = TweetPublisher(browser_manager, llm_service, account)
            engagement = TweetEngagement(browser_manager, account)

            # --- Define actions based on global and account-specific settings ---
            automation_settings = self.global_settings.get(
                "twitter_automation", {}
            )  # Global settings for twitter_automation

            # Determine current ActionConfig: account's action_config > global default action_config
            global_action_config_dict = automation_settings.get(
                "action_config", {}
            )  # Global default action_config
            current_action_config = account.action_config or ActionConfig(
                **global_action_config_dict
            )  # account.action_config is now the primary source if it exists

            # Initialize TweetAnalyzer
            analyzer = TweetAnalyzer(llm_service, account_config=account)

            # Initialize AirdropHunterProcessor
            airdrop_hunter_processor = AirdropHunterProcessor(
                scraper,
                publisher,
                engagement,
                analyzer,
                llm_service,
                account,
                self.file_handler,
            )
            await airdrop_hunter_processor.process(
                current_action_config, self.processed_action_keys
            )

            # Determine LLM settings for different actions:
            # Priority: Account's general LLM override -> Action-specific LLM settings from current_action_config
            llm_for_post = (
                account.llm_settings_override
                or current_action_config.llm_settings_for_post
            )
            llm_for_reply = (
                account.llm_settings_override
                or current_action_config.llm_settings_for_reply
            )
            llm_for_thread_analysis = (
                account.llm_settings_override
                or current_action_config.llm_settings_for_thread_analysis
            )

            # Action 1: Scrape competitor profiles and generate/post new tweets
            # Content sources are now directly from the account config, defaulting to empty lists if not provided.
            competitor_profiles_for_account = account.competitor_profiles

            if (
                current_action_config.enable_competitor_reposts
                and competitor_profiles_for_account
            ):
                logger.info(
                    f"[{account.account_id}] Starting competitor profile scraping and posting using {len(competitor_profiles_for_account)} profiles."
                )
                for profile_url in competitor_profiles_for_account:
                    logger.info(
                        f"[{account.account_id}] Scraping profile: {str(profile_url)}"
                    )

                    tweets_from_profile = await asyncio.to_thread(
                        scraper.scrape_tweets_from_profile,
                        str(profile_url),
                        max_tweets=current_action_config.max_posts_per_competitor_run
                        * 3,
                    )

                    posts_made_this_profile = 0
                    for scraped_tweet in tweets_from_profile:
                        if (
                            posts_made_this_profile
                            >= current_action_config.max_posts_per_competitor_run
                        ):
                            break

                        if (
                            current_action_config.repost_only_tweets_with_media
                            and not scraped_tweet.embedded_media_urls
                        ):
                            logger.debug(
                                f"[{account.account_id}] Skipping tweet {scraped_tweet.tweet_id} (no media)."
                            )
                            continue
                        if (
                            scraped_tweet.like_count
                            < current_action_config.min_likes_for_repost_candidate
                        ):
                            logger.debug(
                                f"[{account.account_id}] Skipping tweet {scraped_tweet.tweet_id} (likes {scraped_tweet.like_count} < min)."
                            )
                            continue
                        if (
                            scraped_tweet.retweet_count
                            < current_action_config.min_retweets_for_repost_candidate
                        ):
                            logger.debug(
                                f"[{account.account_id}] Skipping tweet {scraped_tweet.tweet_id} (retweets {scraped_tweet.retweet_count} < min)."
                            )
                            continue

                        interaction_type = (
                            current_action_config.competitor_post_interaction_type
                        )
                        action_key = f"{interaction_type}_{account.account_id}_{scraped_tweet.tweet_id}"

                        if action_key in self.processed_action_keys:
                            logger.info(
                                f"[{account.account_id}] Action '{action_key}' already processed. Skipping."
                            )
                            continue

                        if (
                            scraped_tweet.is_thread_candidate
                            and current_action_config.enable_thread_analysis
                        ):
                            logger.info(
                                f"[{account.account_id}] Analyzing thread candidacy for tweet {scraped_tweet.tweet_id}..."
                            )
                            is_confirmed = await analyzer.check_if_thread_with_llm(
                                scraped_tweet,
                                custom_llm_settings=llm_for_thread_analysis,
                            )
                            scraped_tweet.is_confirmed_thread = is_confirmed
                            logger.info(
                                f"[{account.account_id}] Thread analysis result for {scraped_tweet.tweet_id}: {is_confirmed}"
                            )

                        interaction_success = False

                        if interaction_type == "repost":
                            prompt = f"Rewrite this tweet in an engaging way: '{scraped_tweet.text_content}' by {scraped_tweet.user_handle or 'a user. Provide only one-two clean sentence. This is used by bot. Text must be ready to post on Twitter.'}."
                            if scraped_tweet.is_confirmed_thread:
                                prompt = f"This tweet is part of a thread. Rewrite its essence engagingly: '{scraped_tweet.text_content}' by {scraped_tweet.user_handle or 'a user. Provide only one-two clean sentence. This is used by bot. Text must be ready to post on Twitter.'}."

                            generated_text = await llm_service.generate_text(
                                prompt=prompt,
                                service_preference=llm_for_reply.service_preference,
                                model_name=llm_for_reply.model_name_override,
                                max_tokens=llm_for_reply.max_tokens,
                                temperature=llm_for_reply.temperature,
                            )

                            new_tweet_content = TweetContent(text=generated_text)
                            logger.info(
                                f"[{account.account_id}] Generating and posting new tweet based on {scraped_tweet.tweet_id}"
                            )
                            interaction_success = await publisher.post_new_tweet(
                                new_tweet_content, llm_settings=llm_for_post
                            )

                        elif interaction_type == "retweet":
                            logger.info(
                                f"[{account.account_id}] Attempting to retweet {scraped_tweet.tweet_id}"
                            )
                            interaction_success = await publisher.retweet_tweet(
                                scraped_tweet
                            )

                        elif interaction_type == "quote_tweet":
                            quote_prompt_templates = current_action_config.prompt_for_quote_tweet_from_competitor
                            quote_prompt_template = random.choice(
                                quote_prompt_templates
                            )
                            quote_prompt = quote_prompt_template.format(
                                user_handle=(scraped_tweet.user_handle or "a user"),
                                tweet_text=scraped_tweet.text_content,
                            )
                            logger.info(
                                f"[{account.account_id}] Attempting to quote tweet {scraped_tweet.tweet_id} with generated text."
                            )
                            # LLM settings for quote tweets could be distinct if added to ActionConfig, for now using llm_for_post
                            interaction_success = await publisher.retweet_tweet(
                                scraped_tweet,
                                quote_text_prompt_or_direct=quote_prompt,
                                llm_settings_for_quote=llm_for_post,
                            )
                        else:
                            logger.warning(
                                f"[{account.account_id}] Unknown competitor_post_interaction_type: {interaction_type}"
                            )
                            continue

                        if interaction_success:
                            self.file_handler.save_processed_action_key(
                                action_key, timestamp=datetime.now().isoformat()
                            )
                            self.processed_action_keys.add(
                                action_key
                            )  # Add to in-memory set for current run
                            posts_made_this_profile += 1
                            await asyncio.sleep(
                                random.uniform(
                                    current_action_config.min_delay_between_actions_seconds,
                                    current_action_config.max_delay_between_actions_seconds,
                                )
                            )
                        else:
                            logger.error(
                                f"[{account.account_id}] Failed to {interaction_type} based on tweet {scraped_tweet.tweet_id}"
                            )

            elif current_action_config.enable_competitor_reposts:
                logger.info(
                    f"[{account.account_id}] Competitor reposts enabled, but no competitor profiles configured for this account."
                )

            # Action 2: Scrape keywords and reply
            target_keywords_for_account = account.target_keywords
            if (
                current_action_config.enable_keyword_replies
                and target_keywords_for_account
            ):
                logger.info(
                    f"[{account.account_id}] Starting keyword scraping and replying for {len(target_keywords_for_account)} keywords."
                )
                for keyword in target_keywords_for_account:
                    logger.info(
                        f"[{account.account_id}] Processing keyword for replies: '{keyword}'"
                    )
                    # Scrape tweets for the keyword
                    tweets_for_keyword = await asyncio.to_thread(
                        scraper.scrape_tweets_by_keyword,
                        keyword,
                        max_tweets=current_action_config.max_replies_per_keyword_run
                        * 2,  # Get more to filter
                    )

                    replies_made_this_keyword = 0
                    for scraped_tweet_to_reply in tweets_for_keyword:
                        if (
                            replies_made_this_keyword
                            >= current_action_config.max_replies_per_keyword_run
                        ):
                            break

                        action_key = f"reply_{account.account_id}_{scraped_tweet_to_reply.tweet_id}"
                        if action_key in self.processed_action_keys:
                            logger.info(
                                f"[{account.account_id}] Already replied or processed tweet {scraped_tweet_to_reply.tweet_id}. Skipping."
                            )
                            continue

                        if (
                            current_action_config.avoid_replying_to_own_tweets
                            and scraped_tweet_to_reply.user_handle
                            and account.account_id.lower()
                            in scraped_tweet_to_reply.user_handle.lower()
                        ):
                            logger.info(
                                f"[{account.account_id}] Skipping own tweet {scraped_tweet_to_reply.tweet_id} for reply."
                            )
                            continue

                        if (
                            current_action_config.reply_only_to_recent_tweets_hours
                            and scraped_tweet_to_reply.created_at
                        ):
                            now_utc = datetime.now(timezone.utc)
                            tweet_age_hours = (
                                now_utc - scraped_tweet_to_reply.created_at
                            ).total_seconds() / 3600
                            if (
                                tweet_age_hours
                                > current_action_config.reply_only_to_recent_tweets_hours
                            ):
                                logger.info(
                                    f"[{account.account_id}] Skipping old tweet {scraped_tweet_to_reply.tweet_id} (age: {tweet_age_hours:.1f}h > limit: {current_action_config.reply_only_to_recent_tweets_hours}h)."
                                )
                                continue

                        # Thread Analysis for context before replying (optional, could make reply more relevant)
                        if (
                            scraped_tweet_to_reply.is_thread_candidate
                            and current_action_config.enable_thread_analysis
                        ):
                            logger.info(
                                f"[{account.account_id}] Analyzing thread candidacy for reply target tweet {scraped_tweet_to_reply.tweet_id}..."
                            )
                            is_confirmed = await analyzer.check_if_thread_with_llm(
                                scraped_tweet_to_reply,
                                custom_llm_settings=llm_for_thread_analysis,
                            )
                            scraped_tweet_to_reply.is_confirmed_thread = is_confirmed
                            logger.info(
                                f"[{account.account_id}] Thread analysis for reply target {scraped_tweet_to_reply.tweet_id}: {is_confirmed}"
                            )

                        # Generate reply text
                        # NOTE I dont care about this for now
                        # reply_prompt_context = (
                        #     "This tweet is part of a thread."
                        #     if scraped_tweet_to_reply.is_confirmed_thread
                        #     else "This is a standalone tweet."
                        # )
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
                        logger.info(
                            f"[{account.account_id}] Generating reply for tweet {scraped_tweet_to_reply.tweet_id}..."
                        )
                        generated_reply_text = await llm_service.generate_text(
                            prompt=reply_prompt,
                            service_preference=llm_for_reply.service_preference,
                            model_name=llm_for_reply.model_name_override,
                            max_tokens=llm_for_reply.max_tokens,
                            temperature=llm_for_reply.temperature,
                        )

                        if not generated_reply_text:
                            logger.error(
                                f"[{account.account_id}] Failed to generate reply text for tweet {scraped_tweet_to_reply.tweet_id}. Skipping."
                            )
                            continue

                        if "FALSE" in generated_reply_text:
                            logger.info(
                                f"Post is not relevant. Skipping. Post: {scraped_tweet_to_reply.text_content}"
                            )
                            continue

                        logger.info(
                            f"[{account.account_id}] Attempting to post reply to tweet {scraped_tweet_to_reply.tweet_id}..."
                        )
                        reply_success = await publisher.reply_to_tweet(
                            scraped_tweet_to_reply, generated_reply_text
                        )

                        if reply_success:
                            self.file_handler.save_processed_action_key(
                                action_key, timestamp=datetime.now().isoformat()
                            )
                            self.processed_action_keys.add(action_key)
                            replies_made_this_keyword += 1
                            await asyncio.sleep(
                                random.uniform(
                                    current_action_config.min_delay_between_actions_seconds,
                                    current_action_config.max_delay_between_actions_seconds,
                                )
                            )
                        else:
                            logger.error(
                                f"[{account.account_id}] Failed to post reply to tweet {scraped_tweet_to_reply.tweet_id}."
                            )
                            # Optionally, add to a temporary blocklist for this session to avoid retrying immediately
                    logger.info(
                        f"[{account.account_id}] Finished processing keyword '{keyword}' for replies."
                    )
            elif current_action_config.enable_keyword_replies:
                logger.info(
                    f"[{account.account_id}] Keyword replies enabled, but no target keywords configured for this account."
                )

            # Action 3: Scrape news/research sites and post summaries/links
            news_sites_for_account = account.news_sites
            research_sites_for_account = account.research_paper_sites
            if current_action_config.enable_content_curation_posts and (
                news_sites_for_account or research_sites_for_account
            ):
                logger.info(
                    f"[{account.account_id}] Content curation from news/research sites is planned."
                )
            elif current_action_config.enable_content_curation_posts:
                logger.info(
                    f"[{account.account_id}] Content curation enabled, but no news/research sites configured for this account."
                )

            # Action 4: Like tweets
            if current_action_config.enable_liking_tweets:
                keywords_to_like = current_action_config.like_tweets_from_keywords or []
                if keywords_to_like:
                    logger.info(
                        f"[{account.account_id}] Starting to like tweets based on {len(keywords_to_like)} keywords."
                    )
                    likes_done_this_run = 0
                    for keyword in keywords_to_like:
                        if (
                            likes_done_this_run
                            >= current_action_config.max_likes_per_run
                        ):
                            break
                        logger.info(
                            f"[{account.account_id}] Searching for tweets with keyword '{keyword}' to like."
                        )
                        tweets_to_potentially_like = await asyncio.to_thread(
                            scraper.scrape_tweets_by_keyword,
                            keyword,
                            max_tweets=current_action_config.max_likes_per_run
                            * 2,  # Fetch more to have options
                        )
                        for tweet_to_like in tweets_to_potentially_like:
                            if (
                                likes_done_this_run
                                >= current_action_config.max_likes_per_run
                            ):
                                break

                            action_key = (
                                f"like_{account.account_id}_{tweet_to_like.tweet_id}"
                            )
                            if action_key in self.processed_action_keys:
                                logger.info(
                                    f"[{account.account_id}] Already liked or processed tweet {tweet_to_like.tweet_id}. Skipping."
                                )
                                continue

                            if (
                                current_action_config.avoid_replying_to_own_tweets
                                and tweet_to_like.user_handle
                                and account.account_id.lower()
                                in tweet_to_like.user_handle.lower()
                            ):
                                logger.info(
                                    f"[{account.account_id}] Skipping own tweet {tweet_to_like.tweet_id} for liking."
                                )
                                continue

                            logger.info(
                                f"[{account.account_id}] Attempting to like tweet {tweet_to_like.tweet_id} from URL: {tweet_to_like.tweet_url}"
                            )
                            like_success = await engagement.like_tweet(
                                tweet_id=tweet_to_like.tweet_id,
                                tweet_url=str(tweet_to_like.tweet_url)
                                if tweet_to_like.tweet_url
                                else None,
                            )

                            if like_success:
                                self.file_handler.save_processed_action_key(
                                    action_key, timestamp=datetime.now().isoformat()
                                )
                                self.processed_action_keys.add(action_key)
                                likes_done_this_run += 1
                                await asyncio.sleep(
                                    random.uniform(
                                        current_action_config.min_delay_between_actions_seconds
                                        / 2,
                                        current_action_config.max_delay_between_actions_seconds
                                        / 2,
                                    )
                                )  # Shorter delay for likes
                            else:
                                logger.warning(
                                    f"[{account.account_id}] Failed to like tweet {tweet_to_like.tweet_id}."
                                )

                elif current_action_config.like_tweets_from_feed:
                    logger.warning(
                        f"[{account.account_id}] Liking tweets from feed is enabled but not yet implemented."
                    )
                else:
                    logger.info(
                        f"[{account.account_id}] Liking tweets enabled, but no keywords specified and feed liking is off."
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
            # Safely log account ID
            account_id_for_log = account_dict.get("account_id", "UnknownAccount")
            if "account" in locals() and hasattr(account, "account_id"):
                account_id_for_log = account.account_id
            logger.info(
                f"--- Finished processing for account: {account_id_for_log} ---"
            )
            # The delay_between_accounts_seconds will now apply after each account finishes,
            # but accounts will start concurrently.
            # If a delay *between starts* is needed, a different mechanism (e.g., semaphore with delays) is required.
            await asyncio.sleep(
                self.global_settings.get("delay_between_accounts_seconds", 10)
            )  # Reduced default for concurrent example

    async def run(self):
        logger.info("Twitter Orchestrator starting...")
        if not self.accounts_data:
            logger.warning(
                "No accounts found in configuration. Orchestrator will exit."
            )
            return

        tasks = []
        for account_dict in self.accounts_data:
            tasks.append(self._process_account(account_dict))

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
    orchestrator = TwitterOrchestrator()
    try:
        asyncio.run(orchestrator.run())
    except KeyboardInterrupt:
        logger.info("Orchestrator run interrupted by user.")
    except Exception as e:
        logger.critical(f"Orchestrator failed with critical error: {e}", exc_info=True)
    finally:
        logger.info("Orchestrator shutdown complete.")
