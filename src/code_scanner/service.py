import asyncio
import json
import logging
import threading
import time
from pathlib import Path
from typing import Dict, List, Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from code_scanner.config import Config, load_config, ConfigError
from code_scanner.git_watcher import GitWatcher, GitError
from code_scanner.scanner import Scanner
from code_scanner.output import OutputGenerator
from code_scanner.issue_tracker import IssueTracker
from code_scanner.models import Issue

from code_scanner.base_client import BaseLLMClient, LLMClientError

logger = logging.getLogger(__name__)

def create_llm_client(config: Config) -> BaseLLMClient:
    """Factory to create LLM client based on config."""
    if config.llm.backend == "lm-studio":
        from code_scanner.lmstudio_client import LMStudioClient
        return LMStudioClient(config.llm)
    elif config.llm.backend == "ollama":
        from code_scanner.ollama_client import OllamaClient
        return OllamaClient(config.llm)
    else:
        raise ValueError(f"Unknown backend: {config.llm.backend}")

class WatcherStatus(BaseModel):
    target_directory: str
    is_running: bool
    total_issues: int

class IssueResponse(BaseModel):
    issues: List[Dict]

class ScannerEngine:
    """Manages a single directory scanning session."""
    
    def __init__(self, config: Config):
        self.config = config
        self.stop_event = threading.Event()
        self.scanner: Optional[Scanner] = None
        self.git_watcher: Optional[GitWatcher] = None
        self.git_thread: Optional[threading.Thread] = None
        self.output_generator: Optional[OutputGenerator] = None
        self.issue_tracker: Optional[IssueTracker] = None
        self.lock = threading.Lock()
        
    def start(self):
        """Start the scanner engine."""
        try:
            self._setup()
            self._start_threads()
            logger.info(f"Started scanner for {self.config.target_directory}")
        except Exception as e:
            logger.error(f"Failed to start scanner for {self.config.target_directory}: {e}")
            self.stop()
            raise

    def stop(self):
        """Stop the scanner engine."""
        self.stop_event.set()
        
        if self.scanner:
            self.scanner.stop()
            
        if self.git_thread and self.git_thread.is_alive():
            self.git_thread.join(timeout=2.0)
            
        logger.info(f"Stopped scanner for {self.config.target_directory}")

    def get_issues(self) -> List[Issue]:
        """Get current list of issues."""
        if self.scanner:
            return self.scanner.get_issues()
        return []

    def _setup(self):
        """Initialize components."""
        # 1. Output Generator (with Auto-Backup logic)
        self.output_generator = OutputGenerator(self.config.output_path)
        self._handle_existing_output()

        # 2. Issue Tracker
        self.issue_tracker = IssueTracker()

        # 3. LLM Client
        try:
            llm_client = create_llm_client(self.config)
            # We skip context limit prompt for daemon mode - rely on config or default
            if llm_client.needs_context_limit() and self.config.llm.context_limit is None:
                logger.warning("Context limit not set in config and required by backend. Using default 16384.")
                llm_client.set_context_limit(16384)
            llm_client.connect()
        except LLMClientError as e:
            raise RuntimeError(f"LLM connection failed: {e}")

        # 4. Git Watcher
        try:
            self.git_watcher = GitWatcher(
                self.config.target_directory,
                self.config.commit_hash
            )
            self.git_watcher.connect()
        except GitError as e:
            raise RuntimeError(f"Git initialization failed: {e}")

        # 5. Scanner
        self.scanner = Scanner(
            config=self.config,
            git_watcher=self.git_watcher,
            llm_client=llm_client,
            issue_tracker=self.issue_tracker,
            output_generator=self.output_generator
        )

    def _handle_existing_output(self):
        """Handle existing output file (Auto-Backup)."""
        output_path = self.config.output_path
        if output_path.exists():
            timestamp = time.strftime('%Y-%m-%d %H:%M:%S')
            backup_path = output_path.parent / f"{output_path.name}.bak"
            try:
                # Append to backup
                content = output_path.read_text()
                with open(backup_path, "a") as f:
                    f.write(f"\n\n{'='*60}\n")
                    f.write(f"Backup created: {timestamp}\n")
                    f.write(f"{'='*60}\n\n")
                    f.write(content)
                logger.info(f"Backed up to {backup_path}")
                # Clear original
                output_path.unlink()
            except Exception as e:
                logger.error(f"Backup failed: {e}")

    def _start_threads(self):
        """Start background threads."""
        self.git_thread = threading.Thread(target=self._git_watch_loop, daemon=True)
        self.git_thread.start()
        self.scanner.start()

    def _git_watch_loop(self):
        """Montior git changes."""
        logger.info("Git watcher started")
        last_state = None
        
        while not self.stop_event.is_set():
            try:
                if self.git_watcher.has_changes_since(last_state):
                    logger.info("Changes detected, triggering scan")
                    self.scanner.signal_refresh()
                    last_state = self.git_watcher.get_state()
            except Exception as e:
                logger.error(f"Git watcher error: {e}")
            
            time.sleep(self.config.git_poll_interval)


# State persistence
STATE_FILE = Path.home() / ".code-scanner" / "state.json"

def save_state():
    """Save watched paths to state file."""
    try:
        paths = [str(k) for k in engines.keys()]
        STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(STATE_FILE, "w") as f:
            json.dump({"watched_paths": paths}, f)
        logger.info(f"Saved state with {len(paths)} paths")
    except Exception as e:
        logger.error(f"Failed to save state: {e}")

def load_state():
    """Load watchers from state file."""
    if not STATE_FILE.exists():
        return
        
    try:
        with open(STATE_FILE, "r") as f:
            data = json.load(f)
            
        for path_str in data.get("watched_paths", []):
            try:
                # Try to load default config or skip if missing
                # Ideally we should store config path too, but for now assuming default
                config = load_config(target_directory=Path(path_str))
                engine = ScannerEngine(config)
                engine.start()
                engines[path_str] = engine
                logger.info(f"Restored watcher for {path_str}")
            except Exception as e:
                logger.error(f"Failed to restore watcher for {path_str}: {e}")
                
    except Exception as e:
        logger.error(f"Failed to load state: {e}")

# Global registry
engines: Dict[str, ScannerEngine] = {}

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Code Scanner Service Starting...")
    load_state()
    yield
    # Shutdown
    logger.info("Shutting down service...")
    for path, engine in engines.items():
        engine.stop()
    engines.clear()

app = FastAPI(lifespan=lifespan)

class AddWatcherRequest(BaseModel):
    path: str
    config_path: Optional[str] = None

@app.post("/watch/add")
async def add_watcher(req: AddWatcherRequest):
    path_str = str(Path(req.path).resolve())
    
    if path_str in engines:
        return {"status": "already_watching", "path": path_str}

    try:
        config = load_config(
            target_directory=Path(req.path),
            config_file=Path(req.config_path) if req.config_path else None
        )
    except ConfigError as e:
        raise HTTPException(status_code=400, detail=str(e))

    engine = ScannerEngine(config)
    try:
        engine.start()
        engines[path_str] = engine
        save_state()  # Persist change
        return {"status": "started", "path": path_str}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to start: {str(e)}")

@app.post("/watch/remove")
async def remove_watcher(req: AddWatcherRequest):
    path_str = str(Path(req.path).resolve())
    
    if path_str not in engines:
        raise HTTPException(status_code=404, detail="Watcher not found")
        
    engine = engines.pop(path_str)
    engine.stop()
    save_state()  # Persist change
    return {"status": "stopped", "path": path_str}

@app.get("/status")
async def get_status() -> List[WatcherStatus]:
    return [
        WatcherStatus(
            target_directory=path,
            is_running=not engine.stop_event.is_set(),
            total_issues=len(engine.get_issues())
        )
        for path, engine in engines.items()
    ]

@app.get("/issues")
async def get_all_issues():
    """Aggregate issues from all watchers for MCP."""
    all_issues = []
    for path, engine in engines.items():
        issues = engine.get_issues()
        # Convert dataclasses to dicts for JSON response
        # We might need to enrich them with project path if not already clear
        for issue in issues:
            issue_dict = issue.__dict__.copy()
            issue_dict["project_path"] = path
            all_issues.append(issue_dict)
    return {"issues": all_issues}
