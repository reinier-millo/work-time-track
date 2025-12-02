import sqlite3
import pandas as pd
from datetime import datetime, timedelta

DB_FILE = "work_log.db"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS work_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            prefix TEXT NOT NULL,
            start_time TIMESTAMP NOT NULL,
            end_time TIMESTAMP,
            duration_seconds REAL
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    ''')
    conn.commit()
    conn.close()

# --- Settings ---
def set_setting(key, value):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)', (key, str(value)))
    conn.commit()
    conn.close()

def get_setting(key, default=None):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('SELECT value FROM settings WHERE key = ?', (key,))
    result = c.fetchone()
    conn.close()
    return result[0] if result else default

# --- Timer Logic ---
def get_active_session():
    """Returns the currently running session (if any) as (id, start_time, prefix)."""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    # Find entry with no end_time
    c.execute('SELECT id, start_time, prefix FROM work_logs WHERE end_time IS NULL ORDER BY start_time DESC LIMIT 1')
    result = c.fetchone()
    conn.close()
    
    if result:
        log_id, start_time_str, prefix = result
        start_time = datetime.fromisoformat(start_time_str) if isinstance(start_time_str, str) else start_time_str
        return log_id, start_time, prefix
    return None

def start_timer(prefix):
    # Check if already running
    active = get_active_session()
    if active:
        return active[0], active[1]

    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    start_time = datetime.now()
    c.execute('INSERT INTO work_logs (prefix, start_time) VALUES (?, ?)', (prefix, start_time))
    log_id = c.lastrowid
    conn.commit()
    conn.close()
    return log_id, start_time

def stop_timer(log_id):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    end_time = datetime.now()
    
    c.execute('SELECT start_time FROM work_logs WHERE id = ?', (log_id,))
    result = c.fetchone()
    if result:
        start_time = datetime.fromisoformat(result[0]) if isinstance(result[0], str) else result[0]
        duration = (end_time - start_time).total_seconds()
        
        c.execute('''
            UPDATE work_logs 
            SET end_time = ?, duration_seconds = ? 
            WHERE id = ?
        ''', (end_time, duration, log_id))
        conn.commit()
    conn.close()
    return end_time

def get_logs():
    conn = sqlite3.connect(DB_FILE)
    df = pd.read_sql_query("SELECT * FROM work_logs WHERE end_time IS NOT NULL ORDER BY start_time DESC", conn)
    conn.close()
    return df

# --- Stats ---
def get_total_time_today():
    conn = sqlite3.connect(DB_FILE)
    today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    c = conn.cursor()
    c.execute('SELECT SUM(duration_seconds) FROM work_logs WHERE start_time >= ? AND end_time IS NOT NULL', (today_start,))
    result = c.fetchone()
    conn.close()
    return result[0] if result and result[0] else 0.0

def get_total_time_week():
    conn = sqlite3.connect(DB_FILE)
    today = datetime.now()
    start_of_week = today - timedelta(days=today.weekday())
    start_of_week = start_of_week.replace(hour=0, minute=0, second=0, microsecond=0)
    
    c = conn.cursor()
    c.execute('SELECT SUM(duration_seconds) FROM work_logs WHERE start_time >= ? AND end_time IS NOT NULL', (start_of_week,))
    result = c.fetchone()
    conn.close()
    return result[0] if result and result[0] else 0.0

def get_stats_for_period(start_date, end_date):
    conn = sqlite3.connect(DB_FILE)
    # Ensure end_date includes the full day
    end_date = end_date + timedelta(days=1)
    
    query = """
        SELECT 
            date(start_time) as day, 
            SUM(duration_seconds) as total_seconds,
            COUNT(*) as entry_count
        FROM work_logs 
        WHERE start_time >= ? AND start_time < ? AND end_time IS NOT NULL
        GROUP BY day
        ORDER BY day
    """
    df_daily = pd.read_sql_query(query, conn, params=(start_date, end_date))
    
    query_all = "SELECT * FROM work_logs WHERE start_time >= ? AND start_time < ? AND end_time IS NOT NULL ORDER BY start_time DESC"
    df_all = pd.read_sql_query(query_all, conn, params=(start_date, end_date))
    
    conn.close()
    return df_daily, df_all
