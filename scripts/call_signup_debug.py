import traceback
from backend.app import create_app
from backend.routes.auth import signup


def run():
    app = create_app({'TESTING': True, 'PROPAGATE_EXCEPTIONS': True})
    with app.test_request_context('/api/signup', method='POST', json={"email":"dbg@example.com","password":"p","full_name":"Dbg","role":"donor"}):
        try:
            resp = signup()
            print('Response:', resp)
        except Exception as e:
            print('Exception during signup:')
            traceback.print_exc()


if __name__ == '__main__':
    run()
