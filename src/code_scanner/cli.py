
import argparse
import asyncio
import logging
import os
import socket
import sys
from pathlib import Path

import httpx
import uvicorn

from code_scanner.config import ServiceConfig

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(os.path.expanduser("~/.code-scanner/service.log"))
    ]
)
logger = logging.getLogger(__name__)

SERVICE_URL = f"http://{ServiceConfig.host}:{ServiceConfig.port}"

def check_server_lock() -> socket.socket:
    """Ensure single instance via port binding."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.bind((ServiceConfig.host, ServiceConfig.lock_port))
        return s
    except OSError:
        print(f"Error: Code Scanner service is already running (Port {ServiceConfig.lock_port} busy).")
        sys.exit(1)

def run_service(args):
    """Start the background service."""
    # check lock
    _lock_socket = check_server_lock()
    
    # Daemonize the process (fork into background)
    if os.fork() > 0:
        # Parent process - exit immediately
        print(f"Code Scanner Service started on {ServiceConfig.host}:{ServiceConfig.port}")
        print(f"Log file: ~/.code-scanner/service.log")
        sys.exit(0)
    
    # Child process continues
    os.setsid()  # Create new session, detach from terminal
    
    # Second fork to prevent zombie processes
    if os.fork() > 0:
        sys.exit(0)
    
    # Redirect standard file descriptors to /dev/null
    sys.stdin = open(os.devnull, 'r')
    sys.stdout = open(os.devnull, 'w')
    sys.stderr = open(os.devnull, 'w')
    
    # Write PID file for later reference
    pid_file = Path(os.path.expanduser("~/.code-scanner/service.pid"))
    pid_file.parent.mkdir(parents=True, exist_ok=True)
    pid_file.write_text(str(os.getpid()))
    
    config = uvicorn.Config(
        "code_scanner.service:app",
        host=ServiceConfig.host,
        port=ServiceConfig.port,
        log_level="info",
        reload=False
    )
    server = uvicorn.Server(config)
    server.run()

def run_add(args):
    """Add a directory to watch."""
    payload = {
        "path": str(Path(args.target_directory).resolve()),
        "config_path": str(Path(args.config).resolve()) if args.config else None
    }
    
    try:
        response = httpx.post(f"{SERVICE_URL}/watch/add", json=payload, timeout=10.0)
        if response.status_code == 200:
            print(f"Successfully started watching: {payload['path']}")
        else:
            print(f"Error ({response.status_code}): {response.text}")
    except httpx.ConnectError:
        print("Error: Could not connect to Code Scanner service. Is it running?")
        sys.exit(1)

def run_remove(args):
    """Remove a watched directory."""
    payload = {
        "path": str(Path(args.target_directory).resolve())
    }
    
    try:
        response = httpx.post(f"{SERVICE_URL}/watch/remove", json=payload, timeout=10.0)
        if response.status_code == 200:
            print(f"Successfully stopped watching: {payload['path']}")
        else:
            print(f"Error ({response.status_code}): {response.text}")
    except httpx.ConnectError:
        print("Error: Could not connect to Code Scanner service. Is it running?")
        sys.exit(1)

def run_list(args):
    """List active watchers."""
    try:
        response = httpx.get(f"{SERVICE_URL}/status", timeout=5.0)
        if response.status_code == 200:
            data = response.json()
            if not data:
                print("No active watchers.")
            else:
                print(f"{'Path':<50} | {'Status':<10} | {'Issues':<5}")
                print("-" * 75)
                for item in data:
                    status = "Running" if item['is_running'] else "Stopped"
                    print(f"{item['target_directory']:<50} | {status:<10} | {item['total_issues']:<5}")
        else:
            print(f"Error ({response.status_code}): {response.text}")
    except httpx.ConnectError:
        print("Error: Could not connect to Code Scanner service. Is it running?")
        sys.exit(1)

def run_mcp(args):
    """Start MCP server (bridge to service)."""
    # Defer import to avoid heavy dependencies if not used
    from code_scanner.mcp_server import run_mcp_server
    try:
        asyncio.run(run_mcp_server())
    except KeyboardInterrupt:
        pass

def parse_args():
    parser = argparse.ArgumentParser(description="Code Scanner - AI-powered local code analysis")
    parser.add_argument("--version", action="version", version="code-scanner 0.2.0")
    
    subparsers = parser.add_subparsers(dest="command", help="Command to execute")
    
    # SERVICE
    parser_service = subparsers.add_parser("service", help="Start the background service daemon")
    
    # CLIENT (Add)
    parser_add = subparsers.add_parser("add", help="Add a project to monitor")
    parser_add.add_argument("target_directory", help="Path to project directory")
    parser_add.add_argument("-c", "--config", help="Path to config.toml")
    
    # CLIENT (Remove)
    parser_remove = subparsers.add_parser("remove", help="Stop monitoring a project")
    parser_remove.add_argument("target_directory", help="Path to project directory")
    
    # CLIENT (List)
    parser_list = subparsers.add_parser("list", help="List monitored projects")

    # MCP
    parser_mcp = subparsers.add_parser("mcp", help="Start MCP server (Stdio)")

    return parser.parse_args()

def main():
    # Ensure log directory exists
    os.makedirs(os.path.expanduser("~/.code-scanner"), exist_ok=True)
    
    args = parse_args()
    
    if args.command == "service":
        run_service(args)
    elif args.command == "add":
        run_add(args)
    elif args.command == "remove":
        run_remove(args)
    elif args.command == "list":
        run_list(args)
    elif args.command == "mcp":
        run_mcp(args)
    else:
        # Default behavior validation or help
        if len(sys.argv) > 1 and os.path.isdir(sys.argv[1]):
            print("Legacy mode deprecated. Please use 'code-scanner add <path>' or 'code-scanner service'.")
            print("Run 'code-scanner --help' for details.")
            sys.exit(1)
        else:
            print("No command provided.")
            print("Run 'code-scanner --help' for usage.")
            sys.exit(1)

if __name__ == "__main__":
    main()
