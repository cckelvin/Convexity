"""
Convexity Filesystem Abstraction.

Provides safe, high-level filesystem operations integrated with the security layer.
Uses pathlib for cross-platform compatibility.
"""

import os
from pathlib import Path
from typing import List, Optional

from .security import validate_path, SecurityError
from .config import config


class FileSystemError(Exception):
    """Raised for filesystem operation errors."""
    pass


def get_current_directory() -> str:
    """Returns the current working directory as a string."""
    return str(Path.cwd().resolve())


def list_directory(path_str: Optional[str] = None) -> List[str]:
    """
    Lists contents of a directory.
    
    Args:
        path_str: Target directory. Defaults to current directory.
        
    Returns:
        List of filenames/directories.
        
    Raises:
        FileSystemError: If path is invalid or not a directory.
    """
    if path_str is None:
        target = Path.cwd()
    else:
        target = validate_path(path_str)
        
    if not target.exists():
        raise FileSystemError(f"Path does not exist: {target}")
    if not target.is_dir():
        raise FileSystemError(f"Path is not a directory: {target}")
        
    try:
        # Return sorted list of names
        return sorted([item.name for item in target.iterdir()])
    except PermissionError:
        raise FileSystemError(f"Permission denied: {target}")


def change_directory(path_str: str) -> str:
    """
    Changes the current working directory.
    
    Args:
        path_str: Target directory.
        
    Returns:
        New current directory path.
        
    Raises:
        FileSystemError: If path is invalid or not a directory.
    """
    target = validate_path(path_str)
    
    if not target.exists():
        raise FileSystemError(f"Directory does not exist: {target}")
    if not target.is_dir():
        raise FileSystemError(f"Not a directory: {target}")
        
    try:
        os.chdir(target)
        return str(target.resolve())
    except Exception as e:
        raise FileSystemError(f"Failed to change directory: {e}")


def make_directory(path_str: str, parents: bool = False) -> str:
    """
    Creates a new directory.
    
    Args:
        path_str: Path for the new directory.
        parents: If True, create parent directories as needed.
        
    Returns:
        Path of the created directory.
    """
    target = validate_path(path_str)
    
    if target.exists():
        raise FileSystemError(f"Path already exists: {target}")
        
    try:
        target.mkdir(parents=parents, exist_ok=False)
        return str(target)
    except Exception as e:
        raise FileSystemError(f"Failed to create directory: {e}")


def touch_file(path_str: str) -> str:
    """
    Creates an empty file or updates its timestamp.
    
    Args:
        path_str: Path for the file.
        
    Returns:
        Path of the touched file.
    """
    target = validate_path(path_str)
    
    try:
        target.touch(exist_ok=True)
        return str(target)
    except Exception as e:
        raise FileSystemError(f"Failed to touch file: {e}")


def read_file(path_str: str) -> str:
    """
    Reads the content of a file.
    
    Args:
        path_str: Path to the file.
        
    Returns:
        File content as string.
    """
    target = validate_path(path_str)
    
    if not target.exists():
        raise FileSystemError(f"File does not exist: {target}")
    if not target.is_file():
        raise FileSystemError(f"Not a file: {target}")
        
    try:
        # Limit size to prevent memory issues
        if target.stat().st_size > config.MAX_OUTPUT_LENGTH:
            return f"[File too large to display ({target.stat().st_size} bytes). Use a text editor.]"
            
        with open(target, 'r', encoding='utf-8', errors='replace') as f:
            return f.read()
    except UnicodeDecodeError:
        return "[Binary file cannot be displayed as text.]"
    except Exception as e:
        raise FileSystemError(f"Failed to read file: {e}")


def write_file(path_str: str, content: str) -> str:
    """
    Writes content to a file.
    
    Args:
        path_str: Path to the file.
        content: Content to write.
        
    Returns:
        Path of the written file.
    """
    target = validate_path(path_str)
    
    # Basic safety: warn if overwriting existing file? 
    # For now, we allow overwrite as per standard touch/write behavior, 
    # but security.py could flag this if REQUIRE_CONFIRMATION is set.
    
    try:
        with open(target, 'w', encoding='utf-8') as f:
            f.write(content)
        return str(target)
    except Exception as e:
        raise FileSystemError(f"Failed to write file: {e}")


def delete_path(path_str: str) -> str:
    """
    Deletes a file or empty directory.
    
    Args:
        path_str: Path to delete.
        
    Returns:
        Success message.
    """
    target = validate_path(path_str)
    
    if not target.exists():
        raise FileSystemError(f"Path does not exist: {target}")
        
    try:
        if target.is_dir():
            # Only allow removing empty dirs for safety in this basic impl
            # Recursive delete would require more complex logic and higher risk
            target.rmdir()
        else:
            target.unlink()
        return f"Deleted: {target}"
    except OSError as e:
        raise FileSystemError(f"Failed to delete: {e}. Directory might not be empty.")
