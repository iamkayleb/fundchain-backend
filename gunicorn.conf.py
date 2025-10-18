# Gunicorn Configuration File for FundChain Backend
# Production WSGI Server Configuration

import multiprocessing

# Server socket
bind = "0.0.0.0:5000"
backlog = 2048

# Worker processes
workers = multiprocessing.cpu_count() * 2 + 1
worker_class = "sync"
worker_connections = 1000
timeout = 30
keepalive = 2

# Restart workers after this many requests, with up to 50% jitter
max_requests = 1000
max_requests_jitter = 50

# Restart workers after this much time
max_worker_lifetime = 3600
max_worker_lifetime_jitter = 300

# Logging
accesslog = "logs/access.log"
errorlog = "logs/error.log"
loglevel = "info"
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(T)s'

# Process naming
proc_name = "fundchain_backend"

# Server mechanics
daemon = False
pidfile = "logs/gunicorn.pid"
user = None
group = None
tmp_upload_dir = None

# SSL (uncomment and configure for HTTPS)
# keyfile = "path/to/keyfile"
# certfile = "path/to/certfile"

# Environment
raw_env = [
    'FLASK_ENV=production',
]

# Preload app for better performance
preload_app = True

# Hook for worker initialization
def on_starting(server):
    server.log.info("Starting FundChain Backend API")

def on_reload(server):
    server.log.info("Reloading FundChain Backend API")

def worker_int(worker):
    worker.log.info("Worker received INT or QUIT signal")

def pre_fork(server, worker):
    server.log.info("Worker spawned (pid: %s)", worker.pid)

def post_fork(server, worker):
    server.log.info("Worker spawned (pid: %s)", worker.pid)

def post_worker_init(worker):
    worker.log.info("Worker initialized (pid: %s)", worker.pid)

def worker_abort(worker):
    worker.log.info("Worker received SIGABRT signal")