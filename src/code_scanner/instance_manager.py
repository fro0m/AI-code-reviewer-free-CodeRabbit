"""Instance manager for multi-instance lock handling.

This module provides centralized lock registry with stale process cleanup,
allowing multiple code-scanner instances to run concurrently for different
target directories.
"""

import hashlib
import json
import logging
import os
import platform
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class InstanceLockError(Exception):
    """Instance lock related error."""
    pass


@dataclass
class InstanceInfo:
    """Information about a running instance."""
    pid: int
    target_directory: str
    config_file: str
    start_time: str
    
    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "pid": self.pid,
            "target_directory": self.target_directory,
            "config_file": self.config_file,
            "start_time": self.start_time,
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "InstanceInfo":
        """Create from dictionary."""
        return cls(
            pid=data["pid"],
            target_directory=data["target_directory"],
            config_file=data["config_file"],
            start_time=data["start_time"],
        )


def get_locks_directory() -> Path:
    """Get the directory for storing lock files.
    
    Returns:
        Path to ~/.code-scanner/locks/
    """
    if platform.system() == "Windows":
        base_dir = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    else:
        base_dir = Path.home()
    
    locks_dir = base_dir / ".code-scanner" / "locks"
    locks_dir.mkdir(parents=True, exist_ok=True)
    return locks_dir


def get_instance_id(target_directory: Path) -> str:
    """Generate a unique instance ID based on target directory.
    
    Args:
        target_directory: The target directory path.
        
    Returns:
        A hash-based unique identifier for the instance.
    """
    # Use absolute path for consistency
    abs_path = str(target_directory.resolve())
    # Create a short hash for the lock file name
    hash_digest = hashlib.sha256(abs_path.encode()).hexdigest()[:16]
    return hash_digest


def get_lock_path(target_directory: Path) -> Path:
    """Get the lock file path for a target directory.
    
    Args:
        target_directory: The target directory path.
        
    Returns:
        Path to the lock file.
    """
    instance_id = get_instance_id(target_directory)
    return get_locks_directory() / f"{instance_id}.lock"


def is_process_running(pid: int) -> bool:
    """Check if a process with the given PID is running.
    
    Args:
        pid: Process ID to check.
        
    Returns:
        True if process is running, False otherwise.
    """
    if platform.system() == "Windows":
        try:
            import ctypes
            kernel32 = ctypes.windll.kernel32
            PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
            handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
            if handle:
                kernel32.CloseHandle(handle)
                return True
            return False
        except Exception:
            return False
    else:
        # Unix-like systems
        try:
            os.kill(pid, 0)
            return True
        except OSError:
            return False


def acquire_lock(target_directory: Path, config_file: Path) -> bool:
    """Acquire a lock for the target directory.
    
    Args:
        target_directory: The target directory to lock.
        config_file: Path to the config file being used.
        
    Returns:
        True if lock was acquired successfully.
        
    Raises:
        InstanceLockError: If another instance is running for this directory.
    """
    lock_path = get_lock_path(target_directory)
    
    # Check for existing lock
    if lock_path.exists():
        try:
            with open(lock_path, "r") as f:
                data = json.load(f)
            info = InstanceInfo.from_dict(data)
            
            # Check if the process is still running
            if is_process_running(info.pid):
                raise InstanceLockError(
                    f"Another instance is already running for directory: {info.target_directory}\n"
                    f"PID: {info.pid}, Started: {info.start_time}\n"
                    f"If this is incorrect, delete the lock file: {lock_path}"
                )
            else:
                # Stale lock - process no longer exists
                logger.info(f"Cleaning up stale lock for PID {info.pid}")
                lock_path.unlink()
        except (json.JSONDecodeError, KeyError, IOError) as e:
            # Corrupted lock file - remove it
            logger.warning(f"Removing corrupted lock file: {e}")
            try:
                lock_path.unlink()
            except IOError:
                pass
    
    # Create new lock
    info = InstanceInfo(
        pid=os.getpid(),
        target_directory=str(target_directory.resolve()),
        config_file=str(config_file.resolve()),
        start_time=datetime.now().isoformat(),
    )
    
    try:
        with open(lock_path, "w") as f:
            json.dump(info.to_dict(), f, indent=2)
        logger.debug(f"Acquired lock: {lock_path}")
        return True
    except IOError as e:
        raise InstanceLockError(f"Could not create lock file: {e}")


def release_lock(target_directory: Path) -> bool:
    """Release the lock for the target directory.
    
    Args:
        target_directory: The target directory to unlock.
        
    Returns:
        True if lock was released, False if lock didn't exist.
    """
    lock_path = get_lock_path(target_directory)
    
    try:
        if lock_path.exists():
            # Verify this is our lock before removing
            with open(lock_path, "r") as f:
                data = json.load(f)
            info = InstanceInfo.from_dict(data)
            
            if info.pid == os.getpid():
                lock_path.unlink()
                logger.debug(f"Released lock: {lock_path}")
                return True
            else:
                logger.warning(f"Lock belongs to different PID: {info.pid} (ours: {os.getpid()})")
                return False
        return False
    except (json.JSONDecodeError, KeyError, IOError) as e:
        logger.warning(f"Error releasing lock: {e}")
        # Try to remove anyway if it's our process
        try:
            lock_path.unlink()
            return True
        except IOError:
            return False


def list_instances() -> list[InstanceInfo]:
    """List all running instances.
    
    Returns:
        List of InstanceInfo for all active instances.
    """
    locks_dir = get_locks_directory()
    instances = []
    
    for lock_file in locks_dir.glob("*.lock"):
        try:
            with open(lock_file, "r") as f:
                data = json.load(f)
            info = InstanceInfo.from_dict(data)
            
            # Only include if process is running
            if is_process_running(info.pid):
                instances.append(info)
            else:
                # Clean up stale lock
                logger.debug(f"Cleaning up stale lock: {lock_file}")
                lock_file.unlink()
        except (json.JSONDecodeError, KeyError, IOError) as e:
            logger.warning(f"Error reading lock file {lock_file}: {e}")
            # Remove corrupted lock
            try:
                lock_file.unlink()
            except IOError:
                pass
    
    return instances


def cleanup_stale_locks() -> int:
    """Clean up all stale lock files.
    
    Returns:
        Number of stale locks cleaned up.
    """
    locks_dir = get_locks_directory()
    cleaned = 0
    
    for lock_file in locks_dir.glob("*.lock"):
        try:
            with open(lock_file, "r") as f:
                data = json.load(f)
            info = InstanceInfo.from_dict(data)
            
            if not is_process_running(info.pid):
                lock_file.unlink()
                cleaned += 1
                logger.info(f"Cleaned up stale lock for PID {info.pid}: {info.target_directory}")
        except (json.JSONDecodeError, KeyError, IOError):
            # Remove corrupted lock
            try:
                lock_file.unlink()
                cleaned += 1
            except IOError:
                pass
    
    return cleaned


def get_instance_for_directory(target_directory: Path) -> Optional[InstanceInfo]:
    """Get instance info for a specific target directory.
    
    Args:
        target_directory: The target directory to check.
        
    Returns:
        InstanceInfo if an instance is running, None otherwise.
    """
    lock_path = get_lock_path(target_directory)
    
    if not lock_path.exists():
        return None
    
    try:
        with open(lock_path, "r") as f:
            data = json.load(f)
        info = InstanceInfo.from_dict(data)
        
        if is_process_running(info.pid):
            return info
        else:
            # Stale lock - clean up
            lock_path.unlink()
            return None
    except (json.JSONDecodeError, KeyError, IOError):
        return None
