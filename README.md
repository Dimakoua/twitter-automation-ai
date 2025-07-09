# Advanced Twitter Automation AI

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python Version](https://img.shields.io/badge/python-3.9%2B-blue.svg)](https://www.python.org/downloads/)
[![Issues](https://img.shields.io/github/issues/ihuzaifashoukat/twitter-automation-ai)](https://github.com/ihuzaifashoukat/twitter-automation-ai/issues)
[![Forks](https://img.shields.io/github/forks/ihuzaifashoukat/twitter-automation-ai)](https://github.com/ihuzaifashoukat/twitter-automation-ai/network/members)
[![Stars](https://img.shields.io/github/stars/ihuzaifashoukat/twitter-automation-ai)](https://github.com/ihuzaifashoukat/twitter-automation-ai/stargazers)
[![Contributors](https://img.shields.io/github/contributors/ihuzaifashoukat/twitter-automation-ai)](https://github.com/ihuzaifashoukat/twitter-automation-ai/graphs/contributors)

> **Note:** This repository is a fork of the original [Advanced Twitter Automation AI](https://github.com/ihuzaifashoukat/twitter-automation-ai) project. It has been modified and tailored to suit specific personal requirements and may differ from the original version.

**Advanced Twitter Automation AI** is a modular Python-based framework designed for automating a wide range of Twitter (now X.com) interactions. It supports multiple accounts and leverages Selenium for robust browser automation, with optional integration of Large Language Models (LLMs) like OpenAI's GPT and Google's Gemini for intelligent content generation, analysis, and engagement.

## Key Changes in This Fork

This fork includes several key improvements and fixes over the original repository to enhance stability, configuration, and reliability:

*   **Core Stability:** The initial codebase has been refactored and cleaned up to ensure the application runs reliably out of the box.
*   **Containerization Support:** A container file has been added, allowing for easy setup and deployment using technologies like Docker.
*   **Robust Publishing:** The tweet publisher has been fixed to handle cases where UI elements are covered by another element (e.g., pop-ups or overlays) by implementing a JavaScript-based "force click". This makes publishing actions significantly more reliable.
*   **Flexible & Secure Configuration:**
    *   You can now securely load account cookies from environment variables, in addition to file paths or direct JSON.
    *   A bug preventing AI service API keys from being correctly read from environment variables has been fixed.
*   **Dynamic Prompts:** The prompt for generating quote tweets (`prompt_for_quote_tweet_from_competitor`) is now an array in the configuration, allowing the bot to randomly select a prompt for more natural and varied content.
*   **Tested LLM Service:** Out of the supported AI services (Gemini, OpenAI, Azure), only **Gemini** has been fully tested and is confirmed to be working in this fork. Other services might require configuration adjustments or code fixes.

## Table of Contents

- [Advanced Twitter Automation AI](#advanced-twitter-automation-ai)
  - [Table of Contents](#table-of-contents)
  - [Features](#features)
  - [Technology Stack](#technology-stack)
  - [Project Structure](#project-structure)
  - [Prerequisites](#prerequisites)
  - [Setup and Configuration](#setup-and-configuration)
    - [1. Clone Repository](#1-clone-repository)
    - [2. Create Virtual Environment](#2-create-virtual-environment)
    - [3. Install Dependencies](#3-install-dependencies)
    - [4. Configure Accounts (`config/accounts.json`)](#4-configure-accounts-configaccountsjson)
    - [5. Configure Global Settings (`config/settings.json`)](#5-configure-global-settings-configsettingsjson)
    - [6. Environment Variables (`.env`) (Optional)](#6-environment-variables-env-optional)
  - [Running the Application](#running-the-application)
  - [Development Notes](#development-notes)
  - [Contributing](#contributing)
  - [Code of Conduct](#code-of-conduct)
  - [License](#license)
  - [TODO / Future Enhancements](#todo--future-enhancements)

## Features

*   **Multi-Account Management:** Seamlessly manage and automate actions for multiple Twitter accounts.
*   **Content Scraping:**
    *   Scrape tweets based on keywords, user profiles, and news/research sites.
    *   Extract tweet content, user information, and engagement metrics.
*   **Content Publishing:**
    *   Post new tweets, including text and media.
    *   Reply to tweets based on various triggers.
    *   Repost (retweet) content from competitor profiles or based on engagement metrics.
*   **LLM Integration:**
    *   Utilize OpenAI (GPT models) and Google Gemini for:
        *   Generating tweet content and replies.
        *   Analyzing tweet threads and sentiment.
        *   Summarizing articles for posting.
    *   Flexible LLM preference settings at global and per-account levels.
*   **Engagement Automation:**
    *   Engage with tweets through likes, replies, and reposts.
    *   Analyze competitor activity and engage strategically.
*   **Configurable Automation:**
    *   Fine-grained control over automation parameters via JSON configuration files.
    *   **Dynamic Prompts:** Use arrays in configuration for prompts (e.g., for quote tweets) to allow for randomized, more natural-sounding content.
    *   **Queue-Based Publishing:** Publish tweets from external systems by dropping simple JSON messages into a file-based queue. Ideal for decoupled architectures.
    *   Per-account overrides for keywords, target profiles, LLM settings, and action behaviors.
    *   **Secure Configuration:** Load sensitive data like API keys and account cookies from environment variables for better security and deployment flexibility.
*   **Robust Browser Automation:** Uses Selenium for interacting with Twitter. Includes a "force click" mechanism to handle dynamic content and UI overlays, making publishing actions significantly more reliable.
*   **Modular Design:** Easily extendable with new features and functionalities.
*   **Logging:** Comprehensive logging for monitoring and debugging.

## Technology Stack

*   **Programming Language:** Python 3.9+
*   **Browser Automation:** Selenium, WebDriver Manager
*   **HTTP Requests:** Requests
*   **Data Validation:** Pydantic
*   **LLM Integration:** Langchain (for Google GenAI), OpenAI SDK
*   **Configuration:** JSON, python-dotenv
*   **Web Interaction:** Fake Headers (for mimicking browser headers)

## Project Structure

The project is organized as follows:

```
twitter-automation-ai/
├── config/
│   ├── accounts.json       # Configuration for multiple Twitter accounts
│   └── settings.json       # Global settings (API keys, automation parameters)
├── src/
│   ├── core/               # Core modules (browser, LLM, config)
│   │   ├── browser_manager.py
│   │   ├── config_loader.py
│   │   └── llm_service.py
│   ├── features/           # Modules for Twitter features (scraper, publisher, etc.)
│   │   ├── scraper.py
│   │   ├── publisher.py
│   │   └── engagement.py
│   ├── utils/              # Utility modules (logger, file handler, etc.)
│   │   ├── logger.py
│   │   ├── file_handler.py
│   │   ├── progress.py
│   │   └── scroller.py
│   ├── data_models.py      # Pydantic models for data structures
│   ├── main.py             # Main orchestrator script
│   ├── publish_queue_messages.py # Script to publish tweets from a file queue
│   └── __init__.py
├── .env                    # Environment variables (optional, for API keys)
├── requirements.txt        # Python dependencies
├── .gitignore              # Specifies intentionally untracked files
├── LICENSE                 # Project license
├── CODE_OF_CONDUCT.md      # Contributor Code of Conduct
├── CONTRIBUTING.md         # Guidelines for contributing
└── README.md               # This file
```

## Prerequisites

*   Python 3.9 or higher.
*   A modern web browser (e.g., Chrome, Firefox) compatible with Selenium.

## Setup and Configuration

Follow these steps to set up and run the project:

### 1. Clone Repository

```bash
git clone https://github.com/ihuzaifashoukat/twitter-automation-ai
cd twitter-automation-ai
```

### 2. Create Virtual Environment

It's highly recommended to use a virtual environment:

```bash
python -m venv venv
# On Windows
venv\Scripts\activate
# On macOS/Linux
source venv/bin/activate
```

### 3. Install Dependencies

Install the required Python packages:

```bash
pip install -r requirements.txt
```

### 4. Configure Accounts (`config/accounts.json`)

This file manages individual Twitter account configurations. It should be an array of account objects.

*   **Key Fields per Account:**
    *   `account_id`: A unique identifier for the account.
    *   `is_active`: Boolean, set to `true` to enable automation for this account.
    *   **Cookie Configuration (Priority Order):** The application uses the first valid cookie source it finds, in this order:
        1.  `cookies`: An array of cookie objects provided directly in the JSON.
        2.  `cookie_file_path`: A path to a JSON file containing an array of cookie objects (e.g., `config/my_account_cookies.json`).
        3.  `cookie_env_name`: The name of an environment variable that contains the cookie data as a JSON string.
    *   `target_keywords`: A list of keywords for this account to track for replies.
    *   `competitor_profiles`: A list of competitor profile URLs to scrape for content ideas.
    *   `llm_settings_override`: Overrides global LLM settings for all actions for this account.
    *   `action_config`: Overrides the global `action_config` from `settings.json`, allowing for account-specific action behaviors (e.g., different delays, enabling/disabling certain actions).

*   **Example `config/accounts.json` showing different cookie methods:**
    ```json
    [
      {
        "account_id": "user_with_cookie_file",
        "is_active": true,
        "cookie_file_path": "config/user_one_cookies.json",
        "target_keywords": ["AI ethics", "future of work"],
        "action_config": {
          "enable_keyword_replies": true,
          "max_replies_per_keyword_run": 2,
          "prompt_for_quote_tweet_from_competitor": [
            "Interesting take from {user_handle}. My thoughts:",
            "Adding to this point by {user_handle}:",
            "Here's another perspective on what {user_handle} said about '{tweet_text}':"
          ]
        }
      },
      {
        "account_id": "user_with_env_var",
        "is_active": true,
        "cookie_env_name": "USER_TWO_COOKIES",
        "competitor_profiles": ["https://x.com/some_competitor"]
      },
      {
        "account_id": "user_with_direct_cookies",
        "is_active": false,
        "cookies": [
          {
            "name": "auth_token",
            "value": "direct_token_value_in_json",
            "domain": ".x.com"
          }
        ]
      }
    ]
    ```
    *(Refer to `src/data_models.py` for the full `AccountConfig` structure.)*

*   **Obtaining Cookies:** Use browser developer tools (e.g., "EditThisCookie" extension) to export cookies for `x.com` after logging in. Save them as a JSON array of cookie objects if using `cookie_file_path`.

### 5. Configure Global Settings (`config/settings.json`)

This file contains global configurations for the application.

*   **Key Sections:**
    *   `api_keys`: Store API keys for LLM services (e.g., `openai_api_key`, `gemini_api_key`).
    *   `twitter_automation`:
        *   `action_config`: Default behaviors for automation actions (e.g., `max_posts_per_run`, `min_likes_for_repost`).
        *   `message_source_to_account_map`: A dictionary mapping a message `source` string to an `account_id` for the queue-based publisher. Example: `{"source_app_1": "tech_blogger_alpha"}`.
        *   `media_directory`: Path to store downloaded media.
    *   `logging`: Configuration for the logger.
    *   `browser_settings`: Settings for Selenium WebDriver (e.g., `headless` mode).

*   **Important Note:** Content source lists like `target_keywords` and `competitor_profiles` are now managed per-account in `config/accounts.json`. The global `action_config` in `settings.json` defines default *how* actions run, which can be overridden per account.

### 6. Environment Variables (`.env`) (Optional)

For sensitive data like API keys, you can use a `.env` file in the project root. `python-dotenv` is included in `requirements.txt` to load these variables.

*   Create a `.env` file:
    ```env
    OPENAI_API_KEY="your_openai_api_key"
    GEMINI_API_KEY="your_gemini_api_key"
    USER_TWO_COOKIES='[{"name": "auth_token", "value": "your_auth_token_from_env", "domain": ".x.com"}]'
    ```
    The application is designed to prioritize environment variables for API keys if available.

## Running the Application

The application has two main entry points:

### 1. Main Orchestrator (`main.py`)

This script runs a comprehensive set of automated actions based on your configuration, such as scraping, content generation, replying, and liking. It iterates through all active accounts and performs the tasks enabled for them.

To run the main orchestrator:
```bash
python src/main.py
```

### 2. Queue-Based Publisher (`publish_queue_messages.py`)

This script provides a simple way to publish tweets from external sources. It watches a directory for new message files (a simple file-based queue) and posts them to the appropriate Twitter account.

To run the queue publisher:
```bash
python src/publish_queue_messages.py
```

**How the Queue Works:**
*   An external process can create a JSON file in the queue directory (default: `/tmp/twitter_queue`).
*   The JSON message should have the following structure:
    ```json
    {
      "type": "generic_message_to_publish",
      "source": "source_app_1",
      "text": "This is the content of the tweet to be published."
    }
    ```
*   The `source` field is used to look up the target `account_id` in the `message_source_to_account_map` setting in your `config/settings.json`.

## Development Notes

*   **Logging:** Detailed logs are output to the console and/or a file. Configuration is in `config/settings.json` and managed by `src/utils/logger.py`.
*   **Customizing AI Prompts:** The personality and behavior of the AI are defined by prompts. Some prompts, like for quote tweets, are configurable in `config/settings.json` under `action_config`. Others, like the main reply prompt in `src/main.py`, are currently defined directly in the code. Modifying these prompts is the primary way to tailor the bot's responses to your specific needs (e.g., for a specific niche like crypto, as seen in the default reply prompt).
*   **Selenium Selectors:** Twitter's (X.com) UI is subject to change. XPath and CSS selectors in `src/features/scraper.py` and `src/features/publisher.py` may require updates if the site structure changes.
*   **LLM Service Status:** As mentioned above, only the Gemini integration is confirmed to be working. If you plan to use OpenAI or Azure, you may need to debug their respective client initializations and API calls in `src/core/llm_service.py`.
*   **Error Handling:** The project includes basic error handling. Enhancements with more specific exception management and retry mechanisms are potential areas for improvement.
*   **Extensibility:** To add new features:
    1.  Define necessary data structures in `src/data_models.py`.
    2.  Create new feature modules within the `src/features/` directory.
    3.  Integrate the new module into the `TwitterOrchestrator` in `src/main.py`.

## Contributing

Contributions are welcome! Please read our [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines on how to contribute, report bugs, or suggest enhancements.

## Code of Conduct

To ensure a welcoming and inclusive environment, this project adheres to a [Code of Conduct](CODE_OF_CONDUCT.md). Please review and follow it in all your interactions with the project.

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.

## TODO / Future Enhancements

*   GUI or web interface for managing accounts, settings, and monitoring.
*   Advanced error handling, including robust retry logic for network issues or UI changes.
*   Integration with proxy services for enhanced multi-account management and anonymity.
*   More detailed per-account activity logging and analytics.
*   Improved AI-driven content analysis and decision-making.