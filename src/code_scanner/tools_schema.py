"""AI tool schema definitions for LLM function calling.

This module contains the JSON schema definitions for the AI tools that can be
invoked by the LLM during code scanning. Each tool allows the LLM to request
additional context from the codebase.
"""

# Tool schema definitions for LLM function calling
AI_TOOLS_SCHEMA = [
    {
        "type": "function",
        "function": {
            "name": "search_text",
            "description": """**VERIFICATION TOOL** - Search repository for text patterns.

**MANDATORY VERIFICATION BEFORE REPORTING:**
- 'unused code/variable' → search_text("variable_name") to find usages
- 'missing import' → search_text("import module") to check imports elsewhere  
- 'dead code' → search_text("function_name") to verify no callers
- 'circular import' → search_text("from X import") to trace import chain

**EXAMPLES:**
- Find all usages of a function: search_text(patterns="process_data")
- Check if variable is used: search_text(patterns="myVar", file_pattern="*.cpp")
- Find regex pattern: search_text(patterns="class.*Service", is_regex=true)

Returns file paths, line numbers, and matching lines. Supports literal text and regex.
Results are paginated (default 50 matches). Use 'offset' parameter to retrieve more results.

**NOTE:** To find references to a specific symbol (function, class, variable), PREFER 'find_usages' which uses ctags for higher accuracy and context.""",
            "parameters": {
                "type": "object",
                "properties": {
                    "patterns": {
                        "oneOf": [
                            {"type": "string"},
                            {"type": "array", "items": {"type": "string"}},
                        ],
                        "description": "Text pattern(s) to search for. Can be a single string or an array of strings. Each pattern is searched as a whole word by default.",
                    },
                    "is_regex": {
                        "type": "boolean",
                        "description": "If true, treat patterns as regular expressions. Default is false (literal text search). Example regex: '(class|def)\\s+MyClass' to find class or function definitions.",
                    },
                    "match_whole_word": {
                        "type": "boolean",
                        "description": "If true (default), match only whole words. If false, match substring anywhere. Ignored when is_regex is true.",
                    },
                    "case_sensitive": {
                        "type": "boolean",
                        "description": "If true, search is case-sensitive. Default is false (case-insensitive).",
                    },
                    "file_pattern": {
                        "type": "string",
                        "description": "Optional glob pattern to filter files (e.g., '*.py', '*.cpp'). If omitted, searches all text files.",
                    },
                    "offset": {
                        "type": "integer",
                        "description": "Skip this many results (for pagination). Use the 'next_offset' value from previous response to get more results.",
                        "minimum": 0,
                    },
                },
                "required": ["patterns"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": """**CONTEXT TOOL** - Read file content to understand context.

**MANDATORY VERIFICATION BEFORE REPORTING:**
- 'missing error handling' → read_file("caller.py") to check calling context
- 'incorrect implementation' → read_file("base_class.py") to read base class
- 'missing cleanup' → read_file to check destructor/cleanup code

**EXAMPLES:**
- Read entire file: read_file(file_path="src/utils.py")
- Read specific lines: read_file(file_path="main.cpp", start_line=50, end_line=100)
- Continue reading large file: read_file(file_path="big.py", start_line=200)

For large files, content is returned in chunks. Use start_line to get subsequent chunks.

**NOTE:** To read a single function, class, or method, PREFER 'get_enclosing_scope' which automatically captures the correct range and is more token-efficient.""",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "Relative path to the file from repository root (e.g., 'src/module/file.ext')",
                    },
                    "start_line": {
                        "type": "integer",
                        "description": "Optional: Line number to start reading from (1-based). Use this to request subsequent chunks of large files.",
                        "minimum": 1,
                    },
                    "end_line": {
                        "type": "integer",
                        "description": "Optional: Line number to stop reading at (1-based, inclusive). If omitted, reads to end or until chunk limit.",
                        "minimum": 1,
                    },
                },
                "required": ["file_path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_directory",
            "description": "List all files and subdirectories in a specific directory. Returns file paths with line counts (for text files). Results are paginated - use 'offset' to get more results if 'has_more' is true.",
            "parameters": {
                "type": "object",
                "properties": {
                    "directory_path": {
                        "type": "string",
                        "description": "Relative path to the directory from repository root (e.g., 'src/utils' or '.' for root)",
                    },
                    "recursive": {
                        "type": "boolean",
                        "description": "If true, list all files recursively in subdirectories. Default is false (only direct children).",
                    },
                    "offset": {
                        "type": "integer",
                        "description": "Skip this many items (for pagination). Use the 'next_offset' value from previous response to get more results.",
                        "minimum": 0,
                    },
                },
                "required": ["directory_path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_file_diff",
            "description": "Get the diff (changes) for a specific file relative to HEAD. Returns only the changed lines in unified diff format, which is much more token-efficient than reading the entire file. Useful for understanding what was modified.",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "Relative path to the file from repository root. Use EXACT path as shown in 'Files to analyze' (e.g., 'src/module/file.py').",
                    },
                    "context_lines": {
                        "type": "integer",
                        "description": "Number of unchanged context lines to include around each change. Default is 3.",
                        "minimum": 0,
                        "maximum": 10,
                    },
                },
                "required": ["file_path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_file_summary",
            "description": "Get a structural summary of a file without reading all content. Returns classes, functions, imports - much more token-efficient than read_file when you only need to understand file structure. Language-agnostic: detects common patterns like 'class', 'def', 'function', 'import', 'require', '#include', etc.",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "Relative path to the file from repository root. Use EXACT path as shown in 'Files to analyze' section (e.g., 'src/module/file.py').",
                    },
                },
                "required": ["file_path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "symbol_exists",
            "description": """**MANDATORY VERIFICATION** - Check if symbol exists before reporting undefined.

**ALWAYS call this BEFORE reporting:**
- 'undefined function X' → symbol_exists("X")
- 'missing class Y' → symbol_exists("Y", symbol_type="class")
- 'unknown method Z' → symbol_exists("Z", symbol_type="method")

**EXAMPLES:**
- Check function exists: symbol_exists(symbol="validate_input")
- Check class exists: symbol_exists(symbol="UserService", symbol_type="class")
- Check any symbol: symbol_exists(symbol="MAX_RETRIES")

Quick O(1) ctags lookup. Returns definition location(s) if found.
NEVER report 'undefined symbol' without calling this first!""",
            "parameters": {
                "type": "object",
                "properties": {
                    "symbol": {
                        "type": "string",
                        "description": "The symbol name to search for (function name, class name, variable, etc.)",
                    },
                    "symbol_type": {
                        "type": "string",
                        "description": "Optional: filter by symbol type. Common types: 'function', 'class', 'method', 'variable', 'constant', 'type', 'interface'. If omitted, searches all types.",
                        "enum": ["function", "class", "method", "variable", "constant", "type", "interface", "any"],
                    },
                },
                "required": ["symbol"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "find_definition",
            "description": """**NAVIGATION TOOL** - Go to symbol definition (like IDE 'Go to Definition').

**USE FOR VERIFICATION:**
- 'incorrect override' → find_definition("base_method") to read base implementation
- 'circular import' → find_definition("imported_class") to trace import chain
- 'wrong inheritance' → find_definition("BaseClass") to check base class

**EXAMPLES:**
- Find function: find_definition(symbol="process_data")
- Find class: find_definition(symbol="UserService", kind="class")

Returns exact file path and line number where symbol is defined.""",
            "parameters": {
                "type": "object",
                "properties": {
                    "symbol": {
                        "type": "string",
                        "description": "The symbol name to find definition for",
                    },
                    "kind": {
                        "type": "string",
                        "description": "Optional: filter by symbol kind (function, class, method, variable, etc.)",
                    },
                },
                "required": ["symbol"],
            },
        },
    },

    {
        "type": "function",
        "function": {
            "name": "find_symbols",
            "description": "Find all symbols matching a pattern across the repository. Supports wildcards (*). Useful for finding all classes ending in 'Service', all functions starting with 'test_', etc.",
            "parameters": {
                "type": "object",
                "properties": {
                    "pattern": {
                        "type": "string",
                        "description": "Pattern to match symbol names. Use * as wildcard (e.g., '*Service', 'test_*', '*Handler*')",
                    },
                    "kind": {
                        "type": "string",
                        "description": "Optional: filter by symbol kind (function, class, method, etc.)",
                    },
                },
                "required": ["pattern"],
            },
        },
    },

    {
        "type": "function",
        "function": {
            "name": "get_enclosing_scope",
            "description": """**CONTEXT TOOL** - Get the function/class/struct containing a specific line.
**PREFER THIS over read_file** when analyzing a specific function or class to save tokens.

**USE FOR CONTEXT:**
- Single line changed → get_enclosing_scope to see full function context
- Understanding what scope a variable belongs to
- Seeing the full method to understand parameter handling

**EXAMPLES:**
- Get function containing line 42: get_enclosing_scope(file_path="src/utils.py", line_number=42)
- Check class structure: get_enclosing_scope(file_path="src/models/user.cpp", line_number=150)

Returns the complete definition (signature, body) of the enclosing scope.""",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "Relative path to the file from repository root",
                    },
                    "line_number": {
                        "type": "integer",
                        "description": "Line number to find enclosing scope for (1-based)",
                        "minimum": 1,
                    },
                },
                "required": ["file_path", "line_number"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "find_usages",
            "description": """**MANDATORY VERIFICATION TOOL** - Find all locations where a symbol is used.
**YOU MUST USE THIS** before claiming any code is unused, dead, or never called.

**REQUIRED WORKFLOW - NEVER SKIP:**
1. Before reporting 'unused function/method' → call find_usages(symbol) FIRST
2. Before reporting 'dead code' → call find_usages(symbol) FIRST  
3. Before reporting 'never called' → call find_usages(symbol) FIRST
4. If find_usages returns ANY results → the code IS used, DO NOT report as unused

**EXAMPLES:**
- Verify function is unused: find_usages(symbol="processData") → if results exist, it IS used
- Check method callers: find_usages(symbol="acquireList") → empty = truly unused
- Find all references: find_usages(symbol="MyClass", include_definitions=true)

**CRITICAL:** If find_usages shows the symbol has callers/references, you MUST NOT report it as dead code or unused. Trust the tool results over your assumptions.

Returns all locations where the symbol appears with file, line, and context.""",
            "parameters": {
                "type": "object",
                "properties": {
                    "symbol": {
                        "type": "string",
                        "description": "Symbol name to find usages for (function, class, variable, etc.)",
                    },
                    "file_path": {
                        "type": "string",
                        "description": "Optional: limit search to this file only",
                    },
                    "include_definitions": {
                        "type": "boolean",
                        "description": "If true, include definition locations. Default is false (usages only).",
                    },
                },
                "required": ["symbol"],
            },
        },
    },
]
