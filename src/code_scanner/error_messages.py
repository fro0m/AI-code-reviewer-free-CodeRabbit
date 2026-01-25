"""Error message constants for code-scanner.

This module contains centralized error message constants to improve
maintainability and consistency across the codebase.
"""


class ConfigErrors:
    """Configuration-related error messages."""

    TARGET_DIR_NOT_EXIST = "Target directory does not exist: {target_directory}"
    TARGET_PATH_NOT_DIR = "Target path is not a directory: {target_directory}"
    CONFIG_FILE_NOT_FOUND = "Configuration file not found: {config_file}\n"
    INVALID_TOML = "Invalid TOML in config file: {e}"
    UNSUPPORTED_SECTIONS = "Unsupported configuration section(s): {sections}\n"
    NO_CHECKS_DEFINED = (
        "No checks defined in configuration file.\n"
        "Add a [[checks]] section with patterns and check names."
    )
    CHECK_MUST_BE_STRING = "Check at index {i} must be a non-empty string"
    CHECK_GROUP_MUST_BE_TABLE = "Check group at index {i} must be a table"
    UNSUPPORTED_CHECK_PARAMS = (
        "Unsupported parameter(s) in [[checks]] group {i}: {params}\n"
        "Valid parameters: pattern, checks"
    )
    CHECK_GROUP_PATTERN_REQUIRED = (
        "Check group at index {i}: 'pattern' must be a non-empty string"
    )
    CHECK_GROUP_CHECKS_MUST_BE_LIST = (
        "Check group at index {i}: 'checks' must be a list"
    )
    CHECK_GROUP_CHECK_MUST_BE_STRING = (
        "Check group {i}, check {j}: must be a non-empty string"
    )
    CHECKS_MUST_BE_LIST_OR_TABLES = (
        "'checks' must be a list of strings or array of tables"
    )
    CHECKS_MUST_BE_NON_EMPTY = "'checks' must be a non-empty list"
    UNSUPPORTED_LLM_PARAMS = (
        "Unsupported parameter(s) in [llm] section: {params}\n"
        "Valid parameters: backend, host, port, model, context_limit, timeout"
    )

    BACKEND_REQUIRED = (
        "\n" + "=" * 70 + "\n"
        "Configuration Error: 'backend' must be specified in [llm] section.\n"
        "=" * 70 + "\n\n"
        "Supported backends:\n"
        "  - \"lm-studio\": LM Studio with OpenAI-compatible API\n"
        "  - \"ollama\": Ollama with native /api/chat endpoint\n\n"
        "Example configuration:\n\n"
        "  [llm]\n"
        "  backend = \"lm-studio\"\n"
        "  host = \"localhost\"\n"
        "  port = 1234\n"
        "  context_limit = 32768\n\n"
        "Or for Ollama:\n\n"
        "  [llm]\n"
        "  backend = \"ollama\"\n"
        "  host = \"localhost\"\n"
        "  port = 11434\n"
        "  model = \"qwen3:4b\"  # Required for Ollama\n"
        "  context_limit = 16384  # Minimum 16384 recommended\n\n"
        "=" * 70
    )

    HOST_REQUIRED = (
        "Configuration Error: 'host' must be specified in [llm] section.\n"
        "Example: host = \"localhost\""
    )

    PORT_REQUIRED = (
        "Configuration Error: 'port' must be specified in [llm] section.\n"
        "Example: port = 1234 (for LM Studio) or port = 11434 (for Ollama)"
    )

    CONTEXT_LIMIT_REQUIRED = (
        "\n" + "=" * 70 + "\n"
        "Configuration Error: 'context_limit' must be specified in [llm] section.\n"
        "=" * 70 + "\n\n"
        "The context_limit parameter is required and defines how much text\n"
        "the LLM can process at once. Common values:\n\n"
        "  - 4096   (small models)\n"
        "  - 8192   (medium models)\n"
        "  - 16384  (recommended minimum)\n"
        "  - 32768  (large context)\n"
        "  - 131072 (very large context)\n\n"
        "Add context_limit to your config.toml:\n\n"
        "  [llm]\n"
        "  backend = \"lm-studio\"\n"
        "  host = \"localhost\"\n"
        "  port = 1234\n"
        "  context_limit = 16384  # <-- Add this line\n\n"
        "Tip: Check your model's context window in LM Studio/Ollama settings.\n"
        "=" * 70
    )

    LLM_CONFIG_ERROR = "LLM Configuration Error: {e}"


class OllamaErrors:
    """Ollama client error messages."""

    MODEL_REQUIRED = (
        "Ollama backend requires 'model' to be specified in config.\n"
        "Add model = \"your-model-name\" to [llm] section."
    )

    NO_MODELS_AVAILABLE = "No models available in Ollama"

    MODEL_NOT_FOUND = (
        "Model '{model}' not found in Ollama.\n"
        "Available models: {available}\n"
        "Pull the model with: ollama pull {model}"
    )

    CONNECTION_ERROR_TEMPLATE = (
        "\n" + "=" * 70 + "\n"
        "CONNECTION ERROR: Ollama\n"
        "=" * 70 + "\n\n"
        "Could not connect to Ollama.\n\n"
        "Connection parameters:\n"
        "  Backend:  ollama\n"
        "  Host:     {host}\n"
        "  Port:     {port}\n"
        "  URL:      {url}\n"
        "  Model:    {model}\n"
        "  Timeout:  {timeout}s\n\n"
        "Please ensure:\n"
        "1. Ollama is running (ollama serve)\n"
        "2. Host and port match your Ollama settings\n"
        "3. Model is pulled (ollama pull {model})\n\n"
        "Error: {error}\n"
        "=" * 70
    )

    INVALID_RESPONSE = "Invalid response from Ollama: {e}"

    CONTEXT_LIMIT_TOO_HIGH = (
        "\n" + "=" * 70 + "\n"
        "CONTEXT LIMIT MISMATCH\n"
        "=" * 70 + "\n\n"
        "Configured context limit ({config_limit}) exceeds model's maximum ({model_limit}).\n\n"
        "To fix this:\n"
        "1. Lower context_limit in config.toml\n"
        "2. Use a model with larger context window\n\n"
        "=" * 70
    )

    NOT_CONNECTED = "Not connected"

    NOT_CONNECTED_OR_NO_CONTEXT = "Not connected or context limit unavailable"

    CONTEXT_OVERFLOW_TEMPLATE = (
        "\n" + "=" * 70 + "\n"
        "CONTEXT LENGTH EXCEEDED\n"
        "=" * 70 + "\n\n"
        "The request exceeded Ollama's context limit.\n"
        "Configured limit: {context_limit} tokens\n\n"
        "To fix this:\n"
        "1. Reduce number of files per batch\n"
        "2. Lower context_limit in config.toml\n"
        "3. Use a model with larger context window\n\n"
        "Error: {error}\n"
        "=" * 70
    )

    LOST_CONNECTION = "Lost connection to Ollama: {e}"

    FAILED_JSON_RESPONSE = (
        "Failed to get valid JSON response after {max_retries} attempts.\n"
        "Last response preview:\n{preview}"
    )


class LMStudioErrors:
    """LM Studio client error messages."""

    NO_MODELS_AVAILABLE = "No models available in LM Studio"

    MODEL_NOT_FOUND = (
        "Model '{model}' not found. "
        "Available models: {available}\n"
        "Load the model in LM Studio first."
    )

    CONNECTION_ERROR_TEMPLATE = (
        "\n" + "=" * 70 + "\n"
        "CONNECTION ERROR: LM Studio\n"
        "=" * 70 + "\n\n"
        "Could not connect to LM Studio.\n\n"
        "Connection parameters:\n"
        "  Backend:  lm-studio\n"
        "  Host:     {host}\n"
        "  Port:     {port}\n"
        "  URL:      {url}\n"
        "  Model:    {model}\n"
        "  Timeout:  {timeout}s\n\n"
        "Please ensure:\n"
        "1. LM Studio is running\n"
        "2. Host and port match your LM Studio settings\n"
        "3. Model is loaded in LM Studio\n\n"
        "Error: {error}\n"
        "=" * 70
    )

    API_ERROR = "LM Studio API error: {e}"

    NOT_CONNECTED = "Not connected"

    NOT_CONNECTED_OR_NO_CONTEXT = "Not connected or context limit unavailable"

    LOST_CONNECTION = "Lost connection to LM Studio: {e}"

    CONTEXT_OVERFLOW_TEMPLATE = (
        "\n" + "=" * 70 + "\n"
        "CONTEXT LENGTH EXCEEDED\n"
        "=" * 70 + "\n\n"
        "The request exceeded LM Studio's context limit.\n"
        "Configured limit: {context_limit} tokens\n\n"
        "To fix this:\n"
        "1. Reduce number of files per batch\n"
        "2. Lower context_limit in config.toml\n"
        "3. Use a model with larger context window\n\n"
        "Error: {error}\n"
        "=" * 70
    )

    FAILED_JSON_RESPONSE = (
        "Failed to get valid JSON response after {max_retries} attempts.\n"
        "Last response preview:\n{preview}"
    )


class GeneralErrors:
    """General error messages."""

    UNSUPPORTED_BACKEND = "Unsupported backend: {backend}"
    INVALID_BACKEND = (
        "Invalid backend '{backend}'. "
        "Must be one of: {valid_backends}"
    )
    CONTEXT_LIMIT_MUST_BE_POSITIVE = "Context limit must be a positive integer"


class GitErrors:
    """Git-related error messages."""

    INVALID_COMMIT_HASH = "Invalid commit hash: {commit_hash}"
    NOT_GIT_REPO = "Not a Git repository: {repo_path}\n"
    NOT_CONNECTED = "Not connected to repository"


class CtagsErrors:
    """Ctags-related error messages."""

    CTAGS_NOT_FOUND = (
        "\n"
        "=" * 70
        + "\n"
        + "UNIVERSAL CTAGS NOT FOUND\n"
        + "=" * 70
        + "\n\n"
        + "Code Scanner requires Universal Ctags for symbol indexing.\n\n"
        + "Please install Universal Ctags:\n\n"
        + "  Ubuntu/Debian:\n"
        + "    sudo apt install universal-ctags\n\n"
        + "  Fedora:\n"
        + "    sudo dnf install ctags\n\n"
        + "  Arch Linux:\n"
        + "    sudo pacman -S ctags\n\n"
        + "  macOS:\n"
        + "    brew install universal-ctags\n\n"
        + "  Windows:\n"
        + "    choco install universalctags\n"
        + "    # or: winget install universalctags.universalctags\n\n"
        + "  From source:\n"
        + "    https://github.com/universal-ctags/ctags\n\n"
        + "=" * 70
    )

    CTAGS_VERSION_CHECK_FAILED = (
        "\n"
        + "=" * 70
        + "\n"
        + "UNIVERSAL CTAGS NOT FOUND\n"
        + "=" * 70
        + "\n\n"
        + "Code Scanner requires Universal Ctags for symbol indexing.\n\n"
        + "The 'ctags' command exists but is not Universal Ctags.\n"
        + "Please install Universal Ctags:\n\n"
        + "  Ubuntu/Debian:\n"
        + "    sudo apt install universal-ctags\n\n"
        + "  Fedora:\n"
        + "    sudo dnf install ctags\n\n"
        + "  Arch Linux:\n"
        + "    sudo pacman -S ctags\n\n"
        + "  macOS:\n"
        + "    brew install universal-ctags\n\n"
        + "  Windows:\n"
        + "    choco install universalctags\n"
        + "    # or: winget install universalctags.universalctags\n\n"
        + "  From source:\n"
        + "    https://github.com/universal-ctags/ctags\n\n"
        + "=" * 70
    )

    CTAGS_TIMEOUT = "Ctags version check timed out. Please verify ctags installation."
    CTAGS_RUN_FAILED = "Failed to run ctags: {e}"
    CTAGS_FAILED = (
        "Ctags failed with exit code {code}:\n{output}"
    )
    CTAGS_INDEX_TIMEOUT = (
        "Ctags timed out after 5 minutes. "
        "Consider increasing timeout or excluding large files."
    )
    CTAGS_RUN_ERROR = "Failed to run ctags: {e}"
    CTAGS_INDEXING_FAILED = "Ctags indexing failed: {error}"


class RipgrepErrors:
    """Ripgrep-related error messages."""

    RIPGREP_NOT_FOUND = (
        "\n"
        + "=" * 70
        + "\n"
        + "RIPGREP NOT FOUND\n"
        + "=" * 70
        + "\n\n"
        + "Code Scanner requires ripgrep for fast code search.\n\n"
        + "Please install ripgrep:\n\n"
        + "  Ubuntu/Debian:\n"
        + "    sudo apt install ripgrep\n\n"
        + "  Fedora:\n"
        + "    sudo dnf install ripgrep\n\n"
        + "  Arch Linux:\n"
        + "    sudo pacman -S ripgrep\n\n"
        + "  macOS:\n"
        + "    brew install ripgrep\n\n"
        + "  Windows:\n"
        + "    choco install ripgrep\n"
        + "    # or: winget install BurntSushi.ripgrep\n\n"
        + "  From source/binaries:\n"
        + "    https://github.com/BurntSushi/ripgrep\n\n"
        + "=" * 70
    )


class CLIErrors:
    """CLI-related error messages."""

    LOCK_FILE_EXISTS = (
        "Another code-scanner instance is already running (PID: {pid}).\n"
        "If you're sure no other instance is running, "
        "remove the lock file:\n  {lock_path}"
    )
    LOCK_FILE_REMOVE_FAILED = "Could not remove invalid lock file: {lock_path}"
    LOCK_FILE_CREATE_FAILED = "Could not create lock file: {e}"
    AT_LEAST_ONE_DIR = "At least one project directory must be specified"
    CONFIG_DIR_MISMATCH = (
        "Number of configs ({num_configs}) must match "
        "number of directories ({num_dirs})"
    )
