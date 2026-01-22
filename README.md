# Code Scanner

![Code Scanner Banner](images/banner.png)

AI-powered code scanner that uses local LLMs (LM Studio or Ollama) to identify issues in your codebase based on configurable checks. **Your code never leaves your machine.**

---

⭐ **Star this project on GitHub to support its development!** [Code-Scanner on GitHub](https://github.com/ubego/Code-Scanner)

---

## Features

- 🏠 **100% Local (Privacy first)**: Uses LM Studio or Ollama with local APIs. All processing happens on your machine, no cloud required.
- 🖥️ **Hardware Efficient**: Designed for small local models. Runs comfortably on consumer GPUs like **NVIDIA RTX 3060**.
- 💰 **Cost Effective**: Zero token costs. Use your local resources instead of expensive API subscriptions.
- 🔍 **Language-agnostic**: Works with any programming language.
- 🧰 **AI Tools for Context Expansion**: LLM can interactively request additional codebase information (find usages, read files, list directories) for sophisticated architectural checks.
- ⚡ **Continuous Monitoring**: Runs in background mode, monitoring Git changes every 30 seconds and scanning indefinitely until stopped (`Ctrl+C`).
- 🔄 **Smart Change Detection**: Efficient git status caching with configurable TTL prevents redundant git operations. When changes are detected mid-scan, continues from current check with refreshed file contents (preserves progress).
- 🔧 **Configurable Checks**: Define checks in plain English via TOML configuration with file pattern support.
- 📊 **Issue Tracking**: Tracks issue lifecycle (new, existing, resolved) with scoped resolution—issues are only resolved for files that were actually scanned.
- 📝 **Real-time Updates**: Output file updates immediately when issues are found (not just at end of scan).
- 🛡️ **Hallucination Prevention**: Validates file paths from LLM responses with helpful suggestions for similar files when paths don't exist.
- 📖 **Daemon-Ready**: Fully uninteractive mode—no prompts, configurable via file only. Supports autostart on all platforms.
- ✅ **Well-Tested**: 92% code coverage with 905 unit tests ensuring reliability and maintainability.

---

## Quick Start

### Prerequisites

1. **Python 3.10 or higher**
2. **Git** (for tracking file changes)
3. **Universal Ctags** (for symbol indexing)
4. **ripgrep** (for fast code search)

### Configuration Reference

### Basic Configuration

**For Ollama:**
```toml
[llm]
backend = "ollama"
host = "localhost"
port = 11434
model = "qwen3:4b"
timeout = 120
context_limit = 16384  # Required

[[checks]]
pattern = "*"
checks = [
    "Check for bugs and issues."
]
```

**For LM Studio:**
```toml
[llm]
backend = "lm-studio"
host = "localhost"
port = 1234
# model = "specific-model-name"  # Optional for LM Studio
context_limit = 32768

[[checks]]
pattern = "*.cpp, *.h"
checks = [
    "Check for memory leaks",
    "Check that RAII is used properly"
]
```

---

## Multi-Project Support

The scanner can monitor **multiple directories (projects) simultaneously** and automatically switch between them based on most recent changes.

### CLI Format

Supports multiple project-config pairs specified at startup:

```bash
# Single project (backward compatible)
code-scanner /path/to/project -c /path/to/config.toml

# Multiple projects
code-scanner /path/to/project1 -c /path/to/config1 /path/to/project2 -c /path/to/config2

# With default configs
code-scanner /path/to/project1 /path/to/project2

# With commit hashes
code-scanner /path/to/project1 --commit abc123 -c /path/to/config1 /path/to/project2 --commit def456
```

*   Each project can have its own configuration file
*   Configs can be specified using `-c` flag or defaults to `code_scanner_config.toml` in each project directory
*   **Active Project Selection:** The project with the **most recent changes** becomes active for checks
    *   Uses existing git change detection algorithm (max mtime_ns among changed files)
    *   Project switching is **non-blocking** - waits for current check to complete
*   **State Preservation:** Each project maintains its own state:
    *   Issue tracker state is preserved in memory for each project
    *   Switching between projects is seamless - previous project state is retained
    *   State is **not persisted** across restarts (starts fresh each time)
*   **LLM Client Management:**
    *   **Smart Switching:** LLM client is **only disconnected and reconnected** when configs differ
    *   **Client Reuse:** If configs are same, existing client is reused (avoids unnecessary reconnections)
    *   **Config Comparison:** Compares backend, host, port, model, and context_limit
*   **Output Files:** Each project has its own output file:
    *   `code_scanner_results.md` in each project directory
    *   Separate results per project for clear separation
*   **Logging:** Single global log file with project prefixes:
    *   Log file location (platform-specific):
        *   Windows: `%APPDATA%\code-scanner\code_scanner.log`
        *   macOS: `~/Library/Application Support/code-scanner/code_scanner.log`
        *   Linux/Unix: `~/.code-scanner/code_scanner.log`
    *   Project prefixes: `[project_0]`, `[project_1]`, etc.
    *   System messages use `[SYSTEM]` prefix
    *   INFO-level logging for project switching (not DEBUG)
*   **Ctags Indexing:** Only active project's ctags index is generated:
    *   Index is regenerated when switching projects
    *   Inactive projects do not maintain ctags index (saves memory)
*   **Single Instance:** One scanner instance monitors all projects:
    *   Single global lock file (platform-specific):
        *   Windows: `%APPDATA%\code-scanner\code_scanner.lock`
        *   macOS: `~/Library/Application Support/code-scanner/code_scanner.lock`
        *   Linux/Unix: `~/.code-scanner/code_scanner.lock`
    *   Prevents multiple scanner instances running simultaneously
*   **Use Case:** User works on one project, then switches to another project without restarting code scanner:
    *   All projects are specified at startup
    *   User doesn't need to restart with different project/config
    *   Seamless switching preserves work context

### Autostart Scripts

All autostart scripts now accept a **full CLI command string** as a single argument. The script automatically detects the code-scanner executable.

**Linux:**
```bash
./scripts/autostart-linux.sh install "/path/to/project1 -c /path/to/config1 /path/to/project2 -c /path/to/config2"
```

**macOS:**
```bash
./scripts/autostart-macos.sh install "/path/to/project1 -c /path/to/config1 /path/to/project2 -c /path/to/config2"
```

**Windows:**
```batch
scripts\autostart-windows.bat install "/path/to/project1 -c /path/to/config1 /path/to/project2 -c /path/to/config2"
```

### Project Switching

When you switch between projects:

1. **Automatic:** The scanner automatically detects which project has the most recent changes and switches to it
2. **Non-blocking:** The current check completes before switching (no interruption)
3. **LLM Client:** If configs differ, old client is disconnected and new one is created. If configs are same, existing client is reused
4. **State:** Previous project state is retained in memory (issues, last scan time, etc.)
5. **Logging:** INFO-level messages show when projects switch (e.g., `[project_0] Switched to active project`)

### Benefits

*   **No Restart Required:** Switch between projects seamlessly without restarting code scanner
*   **Work Context Preserved:** Continue working on project2 while project1's state is preserved in memory
*   **Efficient LLM Usage:** Client is only disconnected/reconnected when necessary (avoids unnecessary reconnections)
*   **Clear Separation:** Each project has its own output file and results are clearly separated

---

## Documentation

For detailed platform-specific setup instructions (including autostart configuration):

*   **[Linux Setup](docs/linux-setup.md)**
*   **[macOS Setup](docs/macos-setup.md)**
*   **[Windows Setup](docs/windows-setup.md)**

---

## Supported LLM Backends

| Backend | Best For | Installation |
|----------|--------------|
| **[LM Studio](https://lmstudio.ai)** | GUI users, trying different models | Download from lmstudio.ai |
| **[Ollama](https://ollama.ai)** | CLI users, automation, simpler setup | `curl -fsSL https://ollama.ai/install.sh \| sh` |

---

## Configuration Reference

### Basic Configuration

**For Ollama:**
```toml
[llm]
backend = "ollama"
host = "localhost"
port = 11434
model = "qwen3:4b"
timeout = 120
context_limit = 16384  # Required

[[checks]]
pattern = "*"
checks = [
    "Check for bugs and issues."
]
```

**For LM Studio:**
```toml
[llm]
backend = "lm-studio"
host = "localhost"
port = 1234
# model = "specific-model-name"  # Optional for LM Studio
context_limit = 32768

[[checks]]
pattern = "*.cpp, *.h"
checks = [
    "Check for memory leaks",
    "Check that RAII is used properly"
]
```

---

## Development

### Project Structure

```bash
src/code_scanner/
├── models.py        # Data models (LLMConfig, Issue, etc.)
├── config.py        # Configuration loading and validation
├── base_client.py   # Abstract base class for LLM clients
├── lmstudio_client.py # LM Studio client
├── ollama_client.py # Ollama client
├── ai_tools.py      # AI tool executor for context expansion
├── text_utils.py    # Text processing utilities
├── git_watcher.py   # Git repository monitoring
├── issue_tracker.py # Issue lifecycle management
├── output.py        # Markdown report generation
├── scanner.py       # AI scanning logic
├── cli.py           # CLI and application coordinator
├── utils.py         # Utility functions
└── __main__.py      # Entry point
```

---

## License

GNU Affero General Public License v3.0

---

## Development

### Running Tests

```bash
uv run pytest                    # Run all tests
uv run pytest -v                 # Verbose output
uv run pytest tests/test_scanner.py -v  # Specific file
uv run pytest --cov=code_scanner --cov-report=term-missing  # Coverage report
uv run pytest --cov=code_scanner --cov-report=html  # Open htmlcov/index.html
```

### Coverage Reports

**Current Coverage:** 91% with 873 tests.

---

## Documentation

For detailed platform-specific setup instructions (including autostart configuration):

*   **[Linux Setup](docs/linux-setup.md)**
*   **[macOS Setup](docs/macos-setup.md)**
*   **[Windows Setup](docs/windows-setup.md)**
