"""Small runner to start the Flask app during development.

Run with:
  python run.py
"""
import os
import sys

# Add current directory to sys.path for imports
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

from app import create_app
from models import db

# Create app instance for WSGI servers (production)
app = create_app()

def main():
  # Ensure tables exist in the default SQLite for development
  with app.app_context():
    try:
      db.create_all()
    except Exception:
      # don't crash on create_all errors in dev
      pass

  app.run(host="0.0.0.0", port=5000, debug=True)


if __name__ == "__main__":
  main()
