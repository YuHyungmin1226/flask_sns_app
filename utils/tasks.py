import os
import threading
from utils.google_drive_utils import drive_manager

# global db_path will be set by app.py
DB_PATH = None

_sync_lock = threading.Lock()
_is_syncing = False
_pending_sync = False

def set_db_path(path):
    global DB_PATH
    DB_PATH = path

def _run_sync():
    global _is_syncing, _pending_sync
    while True:
        try:
            if DB_PATH and not os.environ.get('DATABASE_URL'):
                drive_manager.sync_database(DB_PATH)
        except Exception as e:
            print(f"Sync Error: {e}")
        
        with _sync_lock:
            if _pending_sync:
                _pending_sync = False
            else:
                _is_syncing = False
                break

def scheduled_db_sync_task():
    trigger_db_sync()

def trigger_db_sync():
    global _is_syncing, _pending_sync
    if os.environ.get('DATABASE_URL'):
        return
        
    with _sync_lock:
        if _is_syncing:
            _pending_sync = True
            return
        _is_syncing = True
        
    threading.Thread(target=_run_sync).start()
