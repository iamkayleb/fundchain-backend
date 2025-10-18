"""Small runner to start the Flask app during development.

Run with:
  python backend/run.py
"""
import os
import sys

# Ensure project root is on sys.path so `import backend` works when running this file
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
  sys.path.insert(0, ROOT)

from backend.app import create_app
from backend.models import db


def main():
  app = create_app()

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
