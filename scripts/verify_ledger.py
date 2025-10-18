"""CLI script to verify the ledger."""
from backend import create_app
from backend.ledger import verify_chain, get_chain

app = create_app()

with app.app_context():
    valid, broken = verify_chain()
    chain = get_chain()
    print(f"Ledger length: {len(chain)}")
    print(f"Valid: {valid}")
    if not valid:
        print(f"Broken entries: {broken}")
