"""Configuration loading and validation."""

import logging
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from .utils import get_config_dir
from .error_messages import ConfigErrors 

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib

from .models import LLMConfig, CheckGroup

logger = logging.getLogger(__name__)


class ConfigError(Exception):
    """Configuration error."""

    pass


@dataclass
class Config:
    """Application configuration."""

    target_directory: Path
    config_file: Path
    check_groups: list[CheckGroup]
    commit_hash: Optional[str] = None
    llm: LLMConfig = field(default_factory=LLMConfig)
    debug: bool = False  # Enable debug logging

    # Output file name (in target directory)
    output_file: str = "code_scanner_results.md"
    
    # Home directory files
    log_file: str = "code_scanner.log"
    lock_file: str = "code_scanner.lock"

    # Polling intervals
    git_poll_interval: int = 30  # seconds
    llm_retry_interval: int = 10  # seconds

    # Retry limits
    max_llm_retries: int = 3

    @property
    def home_dir(self) -> Path:
        """Get the code-scanner home directory.
        
        Platform-specific location:
        - Windows: %APPDATA%/code-scanner
        - macOS: ~/Library/Application Support/code-scanner
        - Linux/Unix: ~/.code-scanner
        """
        home = get_config_dir()
        home.mkdir(parents=True, exist_ok=True)
        return home

    @property
    def output_path(self) -> Path:
        """Get full path to output file (in target directory)."""
        return self.target_directory / self.output_file

    @property
    def log_path(self) -> Path:
        """Get full path to log file (in ~/.code-scanner/)."""
        return self.home_dir / self.log_file

    @property
    def lock_path(self) -> Path:
        """Get full path to lock file (in ~/.code-scanner/).
        
        Lock file is global - only one instance of code-scanner can run at a time.
        """
        return self.home_dir / self.lock_file


def load_config(
    target_directory: Path,
    config_file: Optional[Path] = None,
    commit_hash: Optional[str] = None,
    debug: bool = False,
) -> Config:
    """Load configuration from TOML file.

    Args:
        target_directory: Path to the target directory to scan.
        config_file: Optional path to config file. If not provided,
                    looks in the script directory.
        commit_hash: Optional commit hash to compare against.
        debug: Enable debug logging (default: False, INFO level).

    Returns:
        Loaded and validated Config object.

    Raises:
        ConfigError: If config file is missing, invalid, or has no checks.
    """
    # Resolve target directory
    target_directory = target_directory.resolve()
    if not target_directory.exists():
        raise ConfigError(
            ConfigErrors.TARGET_DIR_NOT_EXIST.format(target_directory=target_directory)
        )
    if not target_directory.is_dir():
        raise ConfigError(
            ConfigErrors.TARGET_PATH_NOT_DIR.format(target_directory=target_directory)
        )

    # Find config file
    if config_file is None:
        # Default to target directory
        config_file = target_directory / "code_scanner_config.toml"

    config_file = config_file.resolve()

    if not config_file.exists():
        raise ConfigError(
            f"Configuration file not found: {config_file}\n"
            "Please provide a config file via --config argument or "
            "create code_scanner_config.toml in your project directory."
        )

    # Load TOML
    logger.info(f"Loading configuration from {config_file}")
    try:
        with open(config_file, "rb") as f:
            data = tomllib.load(f)
    except tomllib.TOMLDecodeError as e:
        raise ConfigError(ConfigErrors.INVALID_TOML.format(e=e))

    # Validate no unsupported top-level sections
    SUPPORTED_SECTIONS = {"llm", "checks"}
    unsupported_sections = set(data.keys()) - SUPPORTED_SECTIONS
    if unsupported_sections:
        raise ConfigError(
            f"Unsupported configuration section(s): {sorted(unsupported_sections)}\n"
            f"Supported sections are: {sorted(SUPPORTED_SECTIONS)}\n\n"
            "Remove unsupported sections from your config.toml."
        )

    # Extract checks - support both old format (list of strings) and new format (array of tables)
    checks_data = data.get("checks", [])
    if not checks_data:
        raise ConfigError(
            "No checks defined in configuration file.\n"
            "Add checks to your config.toml:\n"
            '[[checks]]\n'
            'pattern = "*"\n'
            'checks = ["Check for errors", "Check for style issues"]'
        )

    check_groups: list[CheckGroup] = []

    # Detect format: list of strings (old) vs list of dicts (new)
    if isinstance(checks_data, list) and len(checks_data) > 0:
        if isinstance(checks_data[0], str):
            # Old format: list of strings - convert to single group with "*" pattern
            logger.info("Using legacy config format (list of strings). Consider migrating to [[checks]] format.")
            for i, check in enumerate(checks_data):
                if not isinstance(check, str) or not check.strip():
                    raise ConfigError(ConfigErrors.CHECK_MUST_BE_STRING.format(i=i))
            check_groups.append(CheckGroup(
                pattern="*",
                checks=[c.strip() for c in checks_data]
            ))
        elif isinstance(checks_data[0], dict):
            # New format: array of tables
            SUPPORTED_CHECK_PARAMS = {"pattern", "checks"}
            for i, group_data in enumerate(checks_data):
                if not isinstance(group_data, dict):
                    raise ConfigError(ConfigErrors.CHECK_GROUP_MUST_BE_TABLE.format(i=i))

                # Validate no unsupported check parameters
                unsupported_check_params = set(group_data.keys()) - SUPPORTED_CHECK_PARAMS
                if unsupported_check_params:
                    raise ConfigError(
                        f"Unsupported parameter(s) in [[checks]] group {i}: {sorted(unsupported_check_params)}\n"
                        f"Supported parameters are: {sorted(SUPPORTED_CHECK_PARAMS)}\n\n"
                        "Remove unsupported parameters from the [[checks]] section."
                    )

                pattern = group_data.get("pattern", "*")
                checks = group_data.get("checks", [])

                if not isinstance(pattern, str) or not pattern.strip():
                    raise ConfigError(
                        ConfigErrors.CHECK_GROUP_PATTERN_REQUIRED.format(i=i)
                    )

                if not isinstance(checks, list):
                    raise ConfigError(
                        ConfigErrors.CHECK_GROUP_CHECKS_MUST_BE_LIST.format(i=i)
                    )

                # Empty checks list means "ignore files matching this pattern"
                for j, check in enumerate(checks):
                    if not isinstance(check, str) or not check.strip():
                        raise ConfigError(
                            ConfigErrors.CHECK_GROUP_CHECK_MUST_BE_STRING.format(i=i, j=j)
                        )

                check_groups.append(CheckGroup(
                    pattern=pattern.strip(),
                    checks=[r.strip() for r in checks]
                ))
        else:
            raise ConfigError(ConfigErrors.CHECKS_MUST_BE_LIST_OR_TABLES)
    else:
        raise ConfigError(ConfigErrors.CHECKS_MUST_BE_NON_EMPTY)

    # Extract LLM config
    llm_data = data.get("llm", {})
    
    # Validate no unsupported LLM parameters
    SUPPORTED_LLM_PARAMS = {"backend", "host", "port", "model", "timeout", "context_limit"}
    unsupported_llm_params = set(llm_data.keys()) - SUPPORTED_LLM_PARAMS
    if unsupported_llm_params:
        raise ConfigError(
            f"Unsupported parameter(s) in [llm] section: {sorted(unsupported_llm_params)}\n"
            f"Supported parameters are: {sorted(SUPPORTED_LLM_PARAMS)}\n\n"
            "Remove unsupported parameters from the [llm] section."
        )
    
    # Validate required backend field
    if "backend" not in llm_data:
        raise ConfigError(ConfigErrors.BACKEND_REQUIRED)
    
    # Validate required host and port fields
    if "host" not in llm_data:
        raise ConfigError(ConfigErrors.HOST_REQUIRED)
    
    if "port" not in llm_data:
        raise ConfigError(ConfigErrors.PORT_REQUIRED)
    
    # Validate required context_limit field
    if "context_limit" not in llm_data:
        raise ConfigError(ConfigErrors.CONTEXT_LIMIT_REQUIRED)
    
    try:
        llm_config = LLMConfig(
            backend=llm_data["backend"],
            host=llm_data["host"],
            port=llm_data["port"],
            model=llm_data.get("model"),
            timeout=llm_data.get("timeout", 120),
            context_limit=llm_data["context_limit"],  # Now required
        )
    except ValueError as e:
        raise ConfigError(ConfigErrors.LLM_CONFIG_ERROR.format(e=e))

    # Build config
    config = Config(
        target_directory=target_directory,
        config_file=config_file,
        check_groups=check_groups,
        commit_hash=commit_hash,
        llm=llm_config,
        debug=debug,
    )

    total_checks = sum(len(g.checks) for g in config.check_groups)
    logger.info(f"Loaded {len(config.check_groups)} check group(s) with {total_checks} total checks")
    logger.debug(f"LLM backend: {config.llm.backend} at {config.llm.base_url}")

    return config



