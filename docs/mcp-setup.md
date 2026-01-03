# MCP Integration Guide

Code Scanner provides a Model Context Protocol (MCP) server that allows AI IDEs to directly access the issues detected in your projects.

## Prerequisite

Ensure `code-scanner` is available in your path or you know the absolute path to `uv`.
You can verify the MCP server works by running:

```bash
uv run code-scanner mcp
```

(It should hang waiting for input, which is normal for Stdio).

## 1. Cursor

To add Code Scanner to Cursor:

1.  Open **Cursor Settings** -> **Features** -> **MCP**.
2.  Click **+ Add New MCP Server**.
3.  Fill in the details:
    *   **Name**: `code-scanner`
    *   **Type**: `command`
    *   **Command**: `uv run code-scanner mcp` (or full path to your python environment if `uv` is not in global PATH).

### Usage in Cursor
*   Open Chat (Cmd+L / Ctrl+L).
*   Type `@code-scanner` to see available resources.
*   Select `code-scanner://issues` to pull context about current bugs/issues into your chat.

## 2. Windsurf

To add Code Scanner to Windsurf:

1.  Open your home directory configuration: `~/.codeium/windsurf/mcp_config.json`.
2.  Add the following entry to `mcpServers`:

```json
{
  "mcpServers": {
    "code-scanner": {
      "command": "uv",
      "args": [
        "run",
        "code-scanner",
        "mcp"
      ]
    }
  }
}
```

3.  Restart Windsurf.

## 3. Claude Desktop

To add Code Scanner to Claude Desktop:

1.  Open your config file:
    *   **macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
    *   **Windows**: `%APPDATA%\Claude\claude_desktop_config.json`
2.  Add the server configuration:

```json
{
  "mcpServers": {
    "code-scanner": {
      "command": "uv",
      "args": [
        "run",
        "code-scanner",
        "mcp"
      ]
    }
  }
}
```

3.  Restart Claude Desktop.

## 4. GitHub Copilot (VS Code)

To use Code Scanner with GitHub Copilot in VS Code:

1.  Ensure you have the **GitHub Copilot** extension installed.
2.  Create or edit the `.vscode/mcp.json` file in your workspace (project root).
3.  Add the server configuration:

```json
{
  "mcpServers": {
    "code-scanner": {
      "command": "uv",
      "args": [
        "run",
        "code-scanner",
        "mcp"
      ]
    }
  }
}
```

4.  Use Copilot Chat and reference the tool (or just ask about issues).

## 5. Antigravity IDE

To add Code Scanner to Antigravity IDE:

1.  Click the "..." menu in the side panel or find **Manage MCP Servers**.
2.  Select **"Configure MCP Servers"** or open the config file directly (`~/.gemini/antigravity/mcp_config.json` on Linux/macOS or `%USERPROFILE%\.gemini\antigravity\mcp_config.json` on Windows).
3.  Add the server configuration:

```json
{
  "mcpServers": {
    "code-scanner": {
      "command": "uv",
      "args": [
        "run",
        "code-scanner",
        "mcp"
      ]
    }
  }
}
```

4.  Refresh the MCP servers list.

## Troubleshooting


- **"Command not found"**: If your IDE cannot find `uv` or `code-scanner`, use absolute paths.
    - Example: `/Users/username/.local/bin/uv`
- **Connection Refused**: Ensure the Code Scanner **Daemon** is running (`uv run code-scanner service`), as the MCP server connects to it.
