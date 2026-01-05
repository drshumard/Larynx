#!/usr/bin/env python3
"""
Larynx TTS - Audio File Cleanup Script
Deletes audio files older than AUTO_CLEANUP_HOURS (default: 48 hours)
Run via systemd timer or cron
"""

import os
import time
from datetime import datetime, timedelta
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# Configuration
STORAGE_DIR = os.environ.get('STORAGE_DIR', '/var/www/larynx/backend/storage')
AUTO_CLEANUP_HOURS = int(os.environ.get('AUTO_CLEANUP_HOURS', 48))

def cleanup_old_files():
    """Delete audio files older than AUTO_CLEANUP_HOURS."""
    if AUTO_CLEANUP_HOURS <= 0:
        print("Cleanup disabled (AUTO_CLEANUP_HOURS=0)")
        return
    
    storage_path = Path(STORAGE_DIR)
    if not storage_path.exists():
        print(f"Storage directory does not exist: {STORAGE_DIR}")
        return
    
    cutoff_time = time.time() - (AUTO_CLEANUP_HOURS * 3600)
    deleted_count = 0
    deleted_size = 0
    
    print(f"Cleaning up files older than {AUTO_CLEANUP_HOURS} hours...")
    print(f"Storage directory: {STORAGE_DIR}")
    print(f"Cutoff time: {datetime.fromtimestamp(cutoff_time)}")
    
    for file_path in storage_path.glob('*.mp3'):
        try:
            file_stat = file_path.stat()
            if file_stat.st_mtime < cutoff_time:
                file_size = file_stat.st_size
                file_path.unlink()
                deleted_count += 1
                deleted_size += file_size
                print(f"  Deleted: {file_path.name}")
        except Exception as e:
            print(f"  Error deleting {file_path.name}: {e}")
    
    size_mb = deleted_size / (1024 * 1024)
    print(f"\nCleanup complete: {deleted_count} files deleted ({size_mb:.2f} MB freed)")

if __name__ == '__main__':
    cleanup_old_files()
