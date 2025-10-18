#!/usr/bin/env python3
"""
Production server runner for FundChain Backend
Uses Waitress WSGI server (Windows compatible)
"""

import os
from waitress import serve
from app import create_app

def main():
    # Load environment variables
    from dotenv import load_dotenv
    load_dotenv()
    
    # Create Flask app
    app = create_app()
    
    # Configuration
    host = os.getenv('HOST', '0.0.0.0')
    port = int(os.getenv('PORT', 5000))
    threads = int(os.getenv('THREADS', 4))
    
    print(f"🚀 Starting FundChain Backend API on {host}:{port}")
    print(f"📊 Using {threads} threads")
    print(f"🌍 Environment: {os.getenv('FLASK_ENV', 'production')}")
    print(f"🔗 API available at: http://{host}:{port}")
    
    # Serve with Waitress
    serve(
        app,
        host=host,
        port=port,
        threads=threads,
        connection_limit=1000,
        cleanup_interval=30,
        channel_timeout=120,
        log_socket_errors=True
    )

if __name__ == '__main__':
    main()