from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field, HttpUrl, field_validator, model_validator


class AccountCookie(BaseModel):
    name: str
    value: str
    domain: Optional[str] = None
    path: Optional[str] = "/"
    expires: Optional[float] = Field(
        None, alias="expirationDate", description="Timestamp from cookie exporters"
    )
    httpOnly: Optional[bool] = False
    secure: Optional[bool] = False
    sameSite: Optional[Literal["Strict", "Lax", "None"]] = None

    @field_validator("sameSite", mode="before")
    @classmethod
    def adapt_samesite(cls, v: Any) -> Optional[str]:
        """Adapts common 'sameSite' values from browser extensions to the model's expected Literal."""
        if isinstance(v, str):
            v_lower = v.lower()
            if v_lower == "no_restriction":
                return "None"
            # Capitalize to match Literal, e.g., 'lax' -> 'Lax'
            capitalized_v = v_lower.capitalize()
            if capitalized_v in ("Strict", "Lax", "None"):
                return capitalized_v
        return v  # Let Pydantic handle other cases or non-string values


class LLMSettings(BaseModel):
    service_preference: Optional[str] = Field(
        None,
        description="Preferred LLM service for this context: 'gemini', 'openai', 'azure'",
    )
    model_name_override: Optional[str] = Field(
        None, description="Specific model name for the chosen service"
    )
    max_tokens: int = 150
    temperature: Optional[float] = 0.7
    # Add other common LLM parameters as needed


class ActionConfig(BaseModel):  # This can be global or per-account
    # General action timing
    min_delay_between_actions_seconds: int = Field(
        60, description="Minimum delay between any two actions for an account."
    )
    max_delay_between_actions_seconds: int = Field(
        180, description="Maximum delay between any two actions for an account."
    )

    # Competitor Reposting specific controls
    enable_competitor_reposts: bool = Field(
        True, description="Enable reposting based on competitor tweets."
    )
    max_posts_per_competitor_run: int = Field(
        2, description="Max tweets to generate from each competitor profile per run."
    )
    repost_only_tweets_with_media: bool = Field(
        False, description="Only consider competitor tweets with media for reposting."
    )
    min_likes_for_repost_candidate: int = Field(
        0, description="Minimum likes on original competitor tweet to consider."
    )
    min_retweets_for_repost_candidate: int = Field(
        0, description="Minimum retweets on original competitor tweet to consider."
    )
    competitor_post_interaction_type: str = Field(
        "repost",
        description="How to interact with competitor posts: 'repost' (generate new), 'retweet', 'quote_tweet'.",
    )
    prompt_for_quote_tweet_from_competitor: list = Field(
        [
            "Write an insightful comment to quote this tweet by {user_handle}: '{tweet_text}'. Add relevant hashtags."
        ],
        description="Prompt template for generating quote tweet text for competitor's tweet. Use {user_handle} and {tweet_text}.",
    )

    # Keyword Reply specific controls
    enable_keyword_replies: bool = Field(
        True, description="Enable replying to tweets based on keywords."
    )
    max_replies_per_keyword_run: int = Field(
        3, description="Max replies to make per keyword per run."
    )
    reply_only_to_recent_tweets_hours: Optional[int] = Field(
        None,
        description="Only reply to tweets newer than X hours. None means no age limit.",
    )
    avoid_replying_to_own_tweets: bool = Field(
        True,
        description="Prevent replying to the account's own tweets found via keyword search.",
    )

    # Content Curation (News/Research) specific controls
    enable_content_curation_posts: bool = Field(
        True, description="Enable posting curated content from news/research sites."
    )
    max_curated_posts_per_run: int = Field(
        2, description="Max posts from news/research sites per run."
    )

    # Engagement specific controls
    enable_liking_tweets: bool = Field(True, description="Enable liking tweets.")
    max_likes_per_run: int = Field(5, description="Max tweets to like per run.")
    like_tweets_from_keywords: Optional[List[str]] = Field(
        None, description="Keywords to search for tweets to like."
    )
    like_tweets_from_feed: bool = Field(
        False, description="Whether to like tweets from the main home feed."
    )

    # Thread analysis settings
    enable_thread_analysis: bool = Field(
        True,
        description="Enable LLM-based analysis to identify if a tweet is part of a thread.",
    )

    # LLM settings for different actions
    llm_settings_for_post: LLMSettings = Field(default_factory=LLMSettings)
    llm_settings_for_reply: LLMSettings = Field(default_factory=LLMSettings)
    llm_settings_for_thread_analysis: LLMSettings = Field(
        default_factory=lambda: LLMSettings(
            max_tokens=70, temperature=0.2, service_preference="gemini"
        )  # Default to Gemini for this task
    )

    # Airdrop Hunter specific controls
    enable_airdrop_hunter: bool = Field(
        False, description="Enable the Airdrop Hunter module."
    )
    airdrop_hunter_keywords: List[str] = Field(
        default_factory=list, description="Keywords to search for airdrop tweets."
    )
    max_airdrop_tweets_per_run: int = Field(
        5, description="Max airdrop tweets to process per run."
    )
    solana_address: Optional[str] = Field(
        None, description="Solana address to use for airdrops."
    )
    ethereum_address: Optional[str] = Field(
        None, description="Ethereum address to use for airdrops."
    )
    bitcoin_address: Optional[str] = Field(
        None, description="Bitcoin address to use for airdrops."
    )


class AccountConfig(BaseModel):
    account_id: str  # e.g., username or a unique ID
    is_active: bool = True
    # Cookies can be a list of cookie objects or a path to a JSON file containing them
    cookies: Optional[List[AccountCookie]] = None
    cookie_file_path: Optional[str] = None  # Relative to config dir or absolute
    cookie_env_name: Optional[str] = None

    # Optional: For username/password login if implemented
    username: Optional[str] = None
    password: Optional[str] = (
        None  # Consider storing this securely, e.g. env var or encrypted
    )

    # Account-specific settings for content sources (these are now the primary source, not overrides)
    target_keywords: Optional[List[str]] = Field(
        default_factory=list,
        description="Keywords specific to this account for targeting.",
    )
    competitor_profiles: Optional[List[HttpUrl]] = Field(
        default_factory=list,
        description="Competitor profiles specific to this account.",
    )
    news_sites: Optional[List[HttpUrl]] = Field(
        default_factory=list, description="News sites specific to this account."
    )
    research_paper_sites: Optional[List[HttpUrl]] = Field(
        default_factory=list,
        description="Research paper sites specific to this account.",
    )

    # Account-specific LLM preferences (general override for all actions for this account)
    llm_settings_override: Optional[LLMSettings] = Field(
        None, description="General LLM settings override for this account."
    )
    # Account-specific action configurations (can include action-specific LLM settings)
    action_config: Optional[ActionConfig] = Field(
        None,
        description="Specific action configurations for this account. Overrides global action_config.",
    )

    @model_validator(mode="before")
    @classmethod
    def _handle_single_cookie_object(cls, data: Any) -> Any:
        """Allows 'cookies' to be a single dictionary object, wrapping it in a list for robustness."""
        if isinstance(data, dict):
            cookies_val = data.get("cookies")
            if isinstance(cookies_val, dict):
                # If 'cookies' is a single dict, wrap it in a list for validation
                data["cookies"] = [cookies_val]
        return data


class TweetContent(BaseModel):
    text: str  # Can be actual text or a prompt for LLM generation
    media_urls: Optional[List[HttpUrl]] = (
        None  # URLs of media to be downloaded/attached
    )
    local_media_paths: Optional[List[str]] = None  # Paths to already downloaded media


class ScrapedTweet(BaseModel):
    tweet_id: str
    user_name: Optional[str] = None
    user_handle: Optional[str] = None
    user_is_verified: Optional[bool] = False
    created_at: Optional[datetime] = None  # Timestamp of the tweet
    text_content: str

    reply_count: Optional[int] = 0
    retweet_count: Optional[int] = 0
    like_count: Optional[int] = 0
    view_count: Optional[int] = 0  # Or analytics_count

    tags: Optional[List[str]] = []
    mentions: Optional[List[str]] = []
    emojis: Optional[List[str]] = []

    tweet_url: Optional[HttpUrl] = None
    profile_image_url: Optional[HttpUrl] = None

    # Media associated with the tweet
    embedded_media_urls: Optional[List[HttpUrl]] = []

    # Thread identification
    is_thread_candidate: Optional[bool] = Field(
        None,
        description="Initial assessment if tweet might be part of a thread based on simple heuristics from scraper.",
    )
    is_confirmed_thread: Optional[bool] = Field(
        None, description="LLM-confirmed or DOM-confirmed if it's part of a thread."
    )
    thread_context_tweets: Optional[List[Dict[str, Any]]] = Field(
        None,
        description="Brief context of preceding/succeeding tweets if identified as a thread.",
    )

    # For internal use by scraper
    raw_element_data: Optional[Dict[str, Any]] = (
        None  # Store raw Selenium element or its properties if needed
    )


class GlobalSettings(BaseModel):
    # This model can mirror the structure of settings.json for validation
    api_keys: Dict[str, Optional[str]]
    twitter_automation: Dict[
        str, Any
    ]  # Contains default ActionConfig among other things
    logging: Dict[str, str]
    browser_settings: Dict[str, Any]


if __name__ == "__main__":
    # Example usage:
    cookie_example = AccountCookie(
        name="auth_token", value="somevalue", domain=".x.com"
    )
    llm_pref_example = LLMSettings(
        service_preference="azure", model_name_override="gpt-4o-custom-deployment"
    )

    action_override_example = ActionConfig(
        enable_competitor_reposts=False, min_delay_between_actions_seconds=30
    )

    account_example = AccountConfig(
        account_id="user123",
        cookies=[cookie_example],
        competitor_profiles=["https://x.com/anotherprofile"],  # Changed from _override
        llm_settings_override=llm_pref_example,
        action_config=action_override_example,  # Changed from _override
    )
    print("AccountConfig Example:")
    print(account_example.model_dump_json(indent=2))

    tweet_example = ScrapedTweet(
        tweet_id="12345",
        user_name="Test User",
        user_handle="@testuser",
        text_content="This is a test tweet! (1/2)",
        tweet_url="https://x.com/testuser/status/12345",
        is_thread_candidate=True,
    )
    print("\nScrapedTweet Example:")
    print(tweet_example.model_dump_json(indent=2))

    default_action_config = ActionConfig()
    print("\nDefault ActionConfig Example:")
    print(default_action_config.model_dump_json(indent=2))
