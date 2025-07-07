import sqlite3
import logging
import threading
import os
from datetime import datetime
from typing import Dict, List, Optional, Any

class SQLiteHandler(logging.Handler):
    """
    Custom logging handler that writes log records to SQLite database
    Thread-safe and handles automatic database creation
    """
    
    def __init__(self, db_path: str = "logs/app_logs.db"):
        super().__init__()
        self.db_path = db_path
        self.lock = threading.Lock()
        
        # Ensure directory exists
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        
        # Initialize database
        self._init_database()
    
    def _init_database(self):
        """Initialize the SQLite database with logs table"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute('''
                    CREATE TABLE IF NOT EXISTS logs (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp TEXT NOT NULL,
                        logger_name TEXT NOT NULL,
                        level TEXT NOT NULL,
                        level_no INTEGER NOT NULL,
                        message TEXT NOT NULL,
                        pathname TEXT,
                        filename TEXT,
                        funcname TEXT,
                        lineno INTEGER,
                        thread_id INTEGER,
                        thread_name TEXT,
                        process_id INTEGER,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
                
                # Create indexes for better query performance
                conn.execute('''
                    CREATE INDEX IF NOT EXISTS idx_logs_timestamp 
                    ON logs(timestamp)
                ''')
                conn.execute('''
                    CREATE INDEX IF NOT EXISTS idx_logs_level 
                    ON logs(level)
                ''')
                conn.execute('''
                    CREATE INDEX IF NOT EXISTS idx_logs_logger_name 
                    ON logs(logger_name)
                ''')
                conn.commit()
        except Exception as e:
            print(f"Error initializing SQLite logging database: {e}")
    
    def emit(self, record):
        """Emit a log record to SQLite database"""
        try:
            # Try to acquire lock with a very short timeout to prevent hanging
            if self.lock.acquire(blocking=False):
                try:
                    # Format the message
                    message = self.format(record)
                    
                    # Extract timestamp
                    timestamp = datetime.fromtimestamp(record.created).isoformat()
                    
                    # Use a separate connection with very short timeout
                    conn = sqlite3.connect(self.db_path, timeout=0.1)
                    try:
                        conn.execute('''
                            INSERT INTO logs (
                                timestamp, logger_name, level, level_no, message,
                                pathname, filename, funcname, lineno,
                                thread_id, thread_name, process_id
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ''', (
                            timestamp,
                            record.name,
                            record.levelname,
                            record.levelno,
                            message,
                            getattr(record, 'pathname', ''),
                            getattr(record, 'filename', ''),
                            getattr(record, 'funcName', ''),
                            getattr(record, 'lineno', 0),
                            getattr(record, 'thread', 0),
                            getattr(record, 'threadName', ''),
                            getattr(record, 'process', 0)
                        ))
                        conn.commit()
                    finally:
                        conn.close()
                finally:
                    self.lock.release()
            else:
                # If we can't get the lock immediately, skip SQLite and use console
                pass  # Silent fallback - console logging will still work
        except Exception as e:
            # Don't let logging errors crash the application - silent fallback
            pass

class SQLiteLogReader:
    """
    Utility class for reading logs from SQLite database
    Used by the API endpoints to retrieve logs
    """
    
    def __init__(self, db_path: str = "logs/app_logs.db"):
        self.db_path = db_path
    
    def get_logs(self, 
                 log_type: str = 'all',
                 level: str = 'all', 
                 limit: int = 100,
                 offset: int = 0,
                 logger_filter: str = None) -> Dict[str, Any]:
        """
        Retrieve logs from SQLite database
        
        Args:
            log_type: Type of logs (api, error, access, all)
            level: Log level filter (debug, info, warning, error, all)
            limit: Maximum number of logs to return
            offset: Number of logs to skip (for pagination)
            logger_filter: Filter by logger name pattern
        
        Returns:
            Dict containing logs and metadata
        """
        try:
            if not os.path.exists(self.db_path):
                return {
                    'logs': [],
                    'total_count': 0,
                    'message': 'No logs database found',
                    'metadata': {
                        'db_path': self.db_path,
                        'limit': limit,
                        'offset': offset,
                        'level_filter': level,
                        'type_filter': log_type
                    }
                }
            
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row  # Enable column access by name
                
                # Build the query based on filters
                where_conditions = []
                params = []
                
                # Level filter
                if level != 'all':
                    where_conditions.append("UPPER(level) = UPPER(?)")
                    params.append(level)
                
                # Logger name filter for log types
                if log_type == 'api':
                    where_conditions.append("logger_name LIKE ?")
                    params.append('%youtube_api_handler%')
                elif log_type == 'error':
                    where_conditions.append("level_no >= ?")
                    params.append(logging.ERROR)
                elif log_type == 'access':
                    where_conditions.append("logger_name LIKE ?")
                    params.append('%werkzeug%')
                
                # Custom logger filter
                if logger_filter:
                    where_conditions.append("logger_name LIKE ?")
                    params.append(f'%{logger_filter}%')
                
                # Build WHERE clause
                where_clause = ""
                if where_conditions:
                    where_clause = "WHERE " + " AND ".join(where_conditions)
                
                # Get total count
                count_query = f"SELECT COUNT(*) as count FROM logs {where_clause}"
                total_count = conn.execute(count_query, params).fetchone()['count']
                
                # Get logs with pagination
                query = f'''
                    SELECT * FROM logs 
                    {where_clause}
                    ORDER BY timestamp DESC 
                    LIMIT ? OFFSET ?
                '''
                
                cursor = conn.execute(query, params + [limit, offset])
                rows = cursor.fetchall()
                
                # Convert to list of dictionaries
                logs = []
                for row in rows:
                    logs.append({
                        'id': row['id'],
                        'timestamp': row['timestamp'],
                        'logger': row['logger_name'],
                        'level': row['level'],
                        'message': row['message'],
                        'pathname': row['pathname'],
                        'filename': row['filename'],
                        'funcname': row['funcname'],
                        'lineno': row['lineno'],
                        'thread_id': row['thread_id'],
                        'thread_name': row['thread_name'],
                        'process_id': row['process_id'],
                        'created_at': row['created_at']
                    })
                
                # Get database file info
                file_stat = os.stat(self.db_path) if os.path.exists(self.db_path) else None
                file_size = file_stat.st_size if file_stat else 0
                file_modified = datetime.fromtimestamp(file_stat.st_mtime).isoformat() if file_stat else None
                
                return {
                    'logs': logs,
                    'total_count': total_count,
                    'metadata': {
                        'db_path': self.db_path,
                        'file_size_bytes': file_size,
                        'file_size_mb': round(file_size / (1024 * 1024), 2),
                        'file_modified': file_modified,
                        'limit': limit,
                        'offset': offset,
                        'level_filter': level,
                        'type_filter': log_type,
                        'logger_filter': logger_filter,
                        'returned_count': len(logs),
                        'has_more': offset + len(logs) < total_count
                    }
                }
                
        except Exception as e:
            return {
                'logs': [],
                'total_count': 0,
                'error': f'Error reading logs: {str(e)}',
                'metadata': {
                    'db_path': self.db_path,
                    'limit': limit,
                    'offset': offset
                }
            }
    
    def get_log_stats(self) -> Dict[str, Any]:
        """Get statistics about logs in the database"""
        try:
            if not os.path.exists(self.db_path):
                return {'error': 'No logs database found'}
            
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                
                # Get total logs count
                total_logs = conn.execute("SELECT COUNT(*) as count FROM logs").fetchone()['count']
                
                # Get logs by level
                level_stats = {}
                level_results = conn.execute('''
                    SELECT level, COUNT(*) as count 
                    FROM logs 
                    GROUP BY level 
                    ORDER BY count DESC
                ''').fetchall()
                
                for row in level_results:
                    level_stats[row['level']] = row['count']
                
                # Get logs by logger
                logger_stats = {}
                logger_results = conn.execute('''
                    SELECT logger_name, COUNT(*) as count 
                    FROM logs 
                    GROUP BY logger_name 
                    ORDER BY count DESC 
                    LIMIT 10
                ''').fetchall()
                
                for row in logger_results:
                    logger_stats[row['logger_name']] = row['count']
                
                # Get recent activity (last 24 hours)
                recent_activity = conn.execute('''
                    SELECT level, COUNT(*) as count 
                    FROM logs 
                    WHERE datetime(timestamp) > datetime('now', '-1 day')
                    GROUP BY level
                ''').fetchall()
                
                recent_stats = {}
                for row in recent_activity:
                    recent_stats[row['level']] = row['count']
                
                return {
                    'total_logs': total_logs,
                    'by_level': level_stats,
                    'by_logger': logger_stats,
                    'last_24h': recent_stats,
                    'database_path': self.db_path
                }
                
        except Exception as e:
            return {'error': f'Error getting log stats: {str(e)}'}
    
    def cleanup_old_logs(self, days_to_keep: int = 30) -> Dict[str, Any]:
        """Remove logs older than specified days"""
        try:
            if not os.path.exists(self.db_path):
                return {'error': 'No logs database found'}
            
            with sqlite3.connect(self.db_path) as conn:
                # Count logs to be deleted
                count_result = conn.execute('''
                    SELECT COUNT(*) as count 
                    FROM logs 
                    WHERE datetime(timestamp) < datetime('now', '-{} days')
                '''.format(days_to_keep)).fetchone()
                
                logs_to_delete = count_result[0] if count_result else 0
                
                # Delete old logs
                conn.execute('''
                    DELETE FROM logs 
                    WHERE datetime(timestamp) < datetime('now', '-{} days')
                '''.format(days_to_keep))
                
                # Vacuum to reclaim space
                conn.execute('VACUUM')
                conn.commit()
                
                return {
                    'deleted_logs': logs_to_delete,
                    'days_kept': days_to_keep,
                    'message': f'Successfully deleted {logs_to_delete} logs older than {days_to_keep} days'
                }
                
        except Exception as e:
            return {'error': f'Error cleaning up logs: {str(e)}'} 