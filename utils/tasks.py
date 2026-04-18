import os
import threading
from utils.google_drive_utils import drive_manager

# global db_path will be set by app.py
DB_PATH = None

def set_db_path(path):
    global DB_PATH
    DB_PATH = path

def scheduled_db_sync_task():
    try: 
        if DB_PATH and not os.environ.get('DATABASE_URL'): 
            drive_manager.sync_database(DB_PATH)
    except Exception as e: 
        print(f"Sync Error: {e}")

def trigger_db_sync():
    if not os.environ.get('DATABASE_URL'): 
        threading.Thread(target=scheduled_db_sync_task).start()
