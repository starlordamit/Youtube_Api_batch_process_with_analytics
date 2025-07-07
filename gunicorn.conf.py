import os
import multiprocessing
from config import Config

# Server socket
bind = f"{Config.FLASK_HOST}:{Config.FLASK_PORT}"
backlog = 2048

# Worker processes
workers = Config.WORKERS
worker_class = Config.WORKER_CLASS
worker_connections = Config.WORKER_CONNECTIONS
max_requests = Config.MAX_REQUESTS
max_requests_jitter = Config.MAX_REQUESTS_JITTER
timeout = Config.TIMEOUT
keepalive = Config.KEEPALIVE

# Restart workers after this many requests, with up to jitter added variance
preload_app = True
enable_stdio_inheritance = True

# Logging
accesslog = Config.ACCESS_LOG_FILE
errorlog = Config.ERROR_LOG_FILE
loglevel = Config.LOG_LEVEL.lower()
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(D)s'

# Process naming
proc_name = 'youtube_api_server'

# Server mechanics
daemon = False
pidfile = '/tmp/youtube_api.pid'
user = None
group = None
tmp_upload_dir = None

# SSL (if needed)
# keyfile = None
# certfile = None

def when_ready(server):
    server.log.info("YouTube API Server is ready. Accepting connections.")

def worker_int(worker):
    worker.log.info("worker received INT or QUIT signal")
    
def pre_fork(server, worker):
    server.log.info("Worker spawned (pid: %s)", worker.pid)

def post_fork(server, worker):
    server.log.info("Worker spawned (pid: %s)", worker.pid)

def post_worker_init(worker):
    worker.log.info("Worker initialized (pid: %s)", worker.pid)

def worker_abort(worker):
    worker.log.info("Worker aborted (pid: %s)", worker.pid) 