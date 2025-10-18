"""Debug helper: run a signup request using the Flask test client with TESTING=True
so exceptions propagate to the console for diagnosis.
"""
from backend.app import create_app


def run():
    # Create app in testing mode so exceptions are not swallowed
    app = create_app({'TESTING': True, 'PROPAGATE_EXCEPTIONS': True})
    with app.test_client() as client:
        payload = {"email": "debuguser@example.com", "password": "p", "full_name": "Debug User", "role": "donor"}
        resp = client.post('/api/signup', json=payload)
        print('STATUS:', resp.status_code)
        print('DATA:', resp.get_data(as_text=True))


if __name__ == '__main__':
    run()
