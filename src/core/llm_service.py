import logging
from typing import Any, Dict, List, Optional

from langchain_google_genai import ChatGoogleGenerativeAI
from openai import AsyncAzureOpenAI, AsyncOpenAI  # Use async versions
from pydantic import SecretStr

from .config_loader import ConfigLoader

# Initialize logger - Assumes setup_logger has been called by the application entry point.
# If running this module directly for tests, basicConfig might be needed in __main__.
logger = logging.getLogger(__name__)

GEMINI_AVAILABLE = True
OPENAI_AVAILABLE = True

# Standard API key placeholders to check against
API_KEY_PLACEHOLDERS = {
    "gemini_api_key": "YOUR_GEMINI_API_KEY",
    "openai_api_key": "YOUR_OPENAI_API_KEY",
    "azure_openai_api_key": "YOUR_AZURE_OPENAI_API_KEY",
    "azure_openai_endpoint": "YOUR_AZURE_OPENAI_ENDPOINT",
    "azure_openai_deployment": "YOUR_AZURE_OPENAI_DEPLOYMENT_NAME",
}


class LLMService:
    def __init__(self, config_loader: ConfigLoader):
        self.config_loader = config_loader
        self.api_keys: Dict[str, Any] = self.config_loader.get_setting("api_keys", {})
        self.llm_settings: Dict[str, Any] = self.config_loader.get_setting(
            "llm_settings", {}
        )

        self.gemini_client: Optional[ChatGoogleGenerativeAI] = None
        self.openai_client: Optional[AsyncOpenAI] = None
        self.azure_openai_client: Optional[AsyncAzureOpenAI] = None

        self.service_preference_order: List[str] = self.llm_settings.get(
            "service_preference_order",
            ["gemini", "azure", "openai"],  # Default order
        )
        logger.debug(f"Service preference order: {self.service_preference_order}")
        self._initialize_clients()

    def _is_api_key_valid(self, key_name: str, key_value: Optional[str]) -> bool:
        """Checks if an API key is present and not a placeholder."""
        if not key_value:
            return False
        placeholder = API_KEY_PLACEHOLDERS.get(key_name)
        if placeholder and key_value.strip().upper() == placeholder:
            return False
        # Check for common variations if key_name is generic
        if (
            "YOUR_" in key_value.upper() and "_KEY" in key_value.upper()
        ):  # A more generic placeholder check
            return False
        return True

    def _initialize_clients(self):
        # Initialize Gemini client
        if GEMINI_AVAILABLE:
            logger.debug("Checking Gemini configuration...")
            gemini_config = self.llm_settings.get("gemini", {})
            gemini_api_key = self.api_keys.get("gemini_api_key")
            logger.debug(f"Gemini API key: {gemini_api_key}")

            try:
                model_name = gemini_config.get("model", "gemini-pro")  # Default model
                self.gemini_client = ChatGoogleGenerativeAI(
                    model=model_name,
                    api_key=SecretStr(gemini_api_key),
                    temperature=gemini_config.get("temperature", 0.7),
                )
                logger.info(f"Gemini client initialized with model '{model_name}'.")
            except Exception as e:
                logger.error(f"Failed to initialize Gemini client: {e}", exc_info=True)
        else:
            logger.info(
                "Gemini SDK (langchain-google-genai or pydantic) not available. Gemini client cannot be initialized."
            )

        # Initialize OpenAI client (Async)
        if OPENAI_AVAILABLE:
            openai_api_key = self.api_keys.get("openai_api_key")

            try:
                self.openai_client = AsyncOpenAI(api_key=openai_api_key)
                logger.info("AsyncOpenAI client initialized.")
            except Exception as e:
                logger.error(
                    f"Failed to initialize AsyncOpenAI client: {e}", exc_info=True
                )
        else:
            logger.info(
                "OpenAI SDK not available. OpenAI and Azure OpenAI clients cannot be initialized."
            )

        # Initialize Azure OpenAI client (Async)
        # Azure client also depends on OPENAI_AVAILABLE because it uses the same SDK.
        if OPENAI_AVAILABLE:  # Check again as it's a separate client
            azure_config = self.llm_settings.get("azure", {})
            azure_api_key = self.api_keys.get("azure_openai_api_key")
            azure_endpoint = self.api_keys.get("azure_openai_endpoint")
            # Deployment name is critical and acts as the "model" for Azure
            azure_deployment_name = azure_config.get(
                "deployment_name"
            ) or self.api_keys.get("azure_openai_deployment")
            azure_api_version = azure_config.get("api_version") or self.api_keys.get(
                "azure_api_version", "2024-05-01-preview"
            )

            if (
                self._is_api_key_valid("azure_openai_api_key", azure_api_key)
                and self._is_api_key_valid("azure_openai_endpoint", azure_endpoint)
                and self._is_api_key_valid(
                    "azure_openai_deployment", azure_deployment_name
                )
            ):  # Check deployment name validity
                try:
                    self.azure_openai_client = AsyncAzureOpenAI(
                        api_key=azure_api_key,
                        azure_endpoint=azure_endpoint,
                        api_version=azure_api_version,
                        # azure_deployment is passed per-call in AzureOpenAI
                    )
                    logger.info(
                        f"AsyncAzureOpenAI client initialized for endpoint '{azure_endpoint}'. Deployment to be specified per call."
                    )
                except Exception as e:
                    logger.error(
                        f"Failed to initialize AsyncAzureOpenAI client: {e}",
                        exc_info=True,
                    )
            else:
                logger.info(
                    "Azure OpenAI credentials (key, endpoint, or deployment name) not fully configured or are placeholders. Azure OpenAI client not initialized."
                )
        # No separate else for OPENAI_AVAILABLE for Azure as it's covered by OpenAI's check.

    async def generate_text(
        self,
        prompt: str,
        service_preference: Optional[str] = None,
        **call_params: Any,  # Combined model_name, max_tokens, temperature, etc.
    ) -> Optional[str]:
        """
        Generates text using a preferred LLM service with fallback.
        Service-specific parameters (model, max_tokens, temperature) can be passed via call_params
        or will be taken from llm_settings in config.
        """

        services_to_try = list(
            self.service_preference_order
        )  # Start with default/configured order
        if service_preference and service_preference in services_to_try:
            services_to_try.insert(
                0, services_to_try.pop(services_to_try.index(service_preference))
            )  # Move preferred to front
        elif (
            service_preference
        ):  # Preferred service not in default list, add it to front
            services_to_try.insert(0, service_preference)

        logger.debug(f"Service attempt order: {services_to_try}")

        for service_name in services_to_try:
            logger.info(f"Attempting to generate text using {service_name}...")
            service_config = self.llm_settings.get(service_name, {})

            # Merge call_params with defaults from service_config
            # call_params take precedence
            final_params = {**service_config.get("default_params", {}), **call_params}

            # Ensure max_tokens is present, use a global default if not in service_config or call_params
            if "max_tokens" not in final_params:
                final_params["max_tokens"] = self.llm_settings.get(
                    "default_max_tokens", 250
                )

            try:
                if service_name == "gemini" and self.gemini_client:
                    model_to_use = final_params.pop(
                        "model", service_config.get("model", "gemini-pro")
                    )  # Get model from params or config

                    # Map common 'max_tokens' to Gemini's 'max_output_tokens' if present
                    if (
                        "max_tokens" in final_params
                        and "max_output_tokens" not in final_params
                    ):
                        final_params["max_output_tokens"] = final_params.pop(
                            "max_tokens"
                        )

                    # Gemini (langchain) uses 'temperature' etc. directly in invoke
                    # Ensure only valid parameters for ainvoke are passed.
                    # For simplicity, assuming final_params are mostly compatible or ChatGoogleGenerativeAI handles extras.
                    # A more robust way would be to filter final_params against ChatGoogleGenerativeAI.model_fields or similar.
                    response = await self.gemini_client.ainvoke(prompt, **final_params)
                    logger.info(
                        f"Successfully generated text using Gemini model '{model_to_use}'."
                    )
                    return (
                        response.content
                        if hasattr(response, "content")
                        else str(response)
                    )

                elif service_name == "azure" and self.azure_openai_client:
                    # For Azure, 'model' in final_params should be the deployment name.
                    # Or get it from azure_config.deployment_name or api_keys.azure_openai_deployment
                    deployment_name = final_params.pop(
                        "model",
                        service_config.get(
                            "deployment_name",
                            self.api_keys.get("azure_openai_deployment"),
                        ),
                    )
                    if not deployment_name:
                        logger.error(
                            "Azure deployment name not specified for Azure OpenAI call."
                        )
                        continue

                    response = await self.azure_openai_client.chat.completions.create(
                        model=deployment_name,  # This is the deployment name
                        messages=[{"role": "user", "content": prompt}],
                        **final_params,  # Pass temperature, max_tokens, etc.
                    )
                    logger.info(
                        f"Successfully generated text using Azure OpenAI deployment '{deployment_name}'."
                    )
                    return response.choices[0].message.content.strip()

                elif service_name == "openai" and self.openai_client:
                    model_to_use = final_params.pop(
                        "model", service_config.get("model", "gpt-3.5-turbo")
                    )
                    response = await self.openai_client.chat.completions.create(
                        model=model_to_use,
                        messages=[{"role": "user", "content": prompt}],
                        **final_params,
                    )
                    logger.info(
                        f"Successfully generated text using OpenAI model '{model_to_use}'."
                    )
                    return response.choices[0].message.content.strip()

                elif service_name not in ["gemini", "azure", "openai"]:
                    if (
                        service_preference == service_name
                    ):  # Only warn if it was explicitly requested
                        logger.warning(
                            f"Unknown LLM service preference: {service_name}"
                        )
                else:
                    # Client for this service is not initialized
                    logger.info(
                        f"{service_name.capitalize()} client not available or not initialized. Skipping."
                    )

            except Exception as e:
                logger.error(f"Error using {service_name} LLM: {e}", exc_info=True)
                # Continue to the next service in the preference list

        logger.error(
            "All configured LLM services failed or none are available/configured to generate text."
        )
        return None
