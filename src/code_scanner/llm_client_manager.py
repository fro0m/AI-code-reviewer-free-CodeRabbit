"""LLM client manager for multi-project support."""

import threading
from typing import Optional

from code_scanner.base_client import BaseLLMClient
from code_scanner.models import LLMConfig
from code_scanner.utils import logger


class LLMClientManager:
    """Manages LLM client lifecycle for multi-project support."""

    def __init__(self):
        """Initialize the LLM client manager."""
        self._current_client: Optional[BaseLLMClient] = None
        self._current_config: Optional[LLMConfig] = None
        self._lock = threading.Lock()

    def switch_client(self, config: LLMConfig) -> BaseLLMClient:
        """Switch to a different LLM client configuration.

        IMPORTANT: Only disconnects and reconnects if configs are different.
        If configs are the same, reuses existing client.
        This is non-blocking - disconnects after current operations complete.
        Returns the current client (may be new or reused).

        Args:
            config: The LLM configuration to switch to.

        Returns:
            The current LLM client (new or reused).
        """
        with self._lock:
            # Check if we need to switch
            if self._current_config is not None and self._configs_equal(
                self._current_config, config
            ):
                # Configs are the same - reuse existing client
                logger.debug(f"Reusing existing LLM client (backend={config.backend}, model={config.model})")
                return self._current_client

            # Configs differ - disconnect current and create new
            logger.info(f"Switching LLM client (backend={config.backend}, model={config.model})")
            self._disconnect_current()

            # Create new client
            new_client = self._create_client_from_config(config)
            self._current_client = new_client
            self._current_config = config

            return new_client

    def get_current_client(self) -> Optional[BaseLLMClient]:
        """Get current LLM client.

        Returns:
            The current LLM client, or None if no client is initialized.
        """
        with self._lock:
            return self._current_client

    def get_current_config(self) -> Optional[LLMConfig]:
        """Get current LLM configuration.

        Returns:
            The current LLM configuration, or None if no client is initialized.
        """
        with self._lock:
            return self._current_config

    def _disconnect_current(self) -> None:
        """Disconnect current client if it exists."""
        if self._current_client is not None:
            # Note: BaseLLMClient doesn't have explicit disconnect
            # We just release the reference and let it be garbage collected
            logger.debug("Disconnecting current LLM client")
            self._current_client = None
            self._current_config = None

    def _configs_equal(self, config1: LLMConfig, config2: LLMConfig) -> bool:
        """Check if two LLM configs are functionally equivalent.

        Args:
            config1: First configuration.
            config2: Second configuration.

        Returns:
            True if configs are functionally equivalent.
        """
        return (
            config1.backend == config2.backend and
            config1.host == config2.host and
            config1.port == config2.port and
            config1.model == config2.model and
            config1.context_limit == config2.context_limit
        )

    @staticmethod
    def _create_client_from_config(config: LLMConfig) -> BaseLLMClient:
        """Create an LLM client from configuration.

        Args:
            config: The LLM configuration.

        Returns:
            The created LLM client.
        """
        if config.backend == "lm-studio":
            from code_scanner.lmstudio_client import LMStudioClient
            return LMStudioClient(
                host=config.host,
                port=config.port,
                model=config.model,
                timeout=config.timeout,
                context_limit=config.context_limit,
            )
        elif config.backend == "ollama":
            from code_scanner.ollama_client import OllamaClient
            return OllamaClient(
                host=config.host,
                port=config.port,
                model=config.model,
                timeout=config.timeout,
                context_limit=config.context_limit,
            )
        else:
            raise ValueError(f"Unsupported backend: {config.backend}")
