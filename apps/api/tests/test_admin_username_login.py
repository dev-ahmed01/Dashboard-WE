"""Optional administrator username alias: local preview sign-in without schema changes."""
from sqlalchemy import select

from tests.test_persona_qa import client
from app import main
from app.db import SessionLocal
from app.models import User
from app.security import hasher


def test_admin_username_alias_and_existing_email_login(client, monkeypatch):
    settings = main.get_settings()
    monkeypatch.setattr(settings, 'admin_username', 'admin')

    # An existing installation retains its account and email address.
    old = client.post('/api/auth/login', json={
        'email': 'owner@example.test', 'password': 'local_test_only_password_12345'
    })
    assert old.status_code == 200, old.text
    old_token = old.json()['access_token']

    # Simulate a one-time operator reset of a disposable local test account.
    # Existing strong-password rules for team creation/password changes stay intact.
    with SessionLocal() as db:
        owner = db.scalar(select(User).where(User.email == 'owner@example.test'))
        assert owner and owner.role == 'admin'
        owner.password_hash = hasher.hash('short-demo')
        owner.auth_version += 1
        db.commit()

    alias = client.post('/api/auth/login', json={
        'identifier': ' ADMIN ', 'password': 'short-demo'
    })
    assert alias.status_code == 200, alias.text
    assert alias.json()['user']['role'] == 'admin'
    assert alias.json()['user']['email'] == 'owner@example.test'

    email = client.post('/api/auth/login', json={
        'identifier': 'owner@example.test', 'password': 'short-demo'
    })
    assert email.status_code == 200
    assert client.get('/api/auth/me', headers={
        'Authorization': 'Bearer ' + old_token
    }).status_code == 401
    assert client.post('/api/auth/login', json={
        'identifier': 'admin', 'password': 'incorrect'
    }).status_code == 401
    assert client.post('/api/auth/login', json={
        'identifier': ' ', 'password': 'short-demo'
    }).status_code == 422


def test_alias_is_disabled_unless_explicitly_configured(client, monkeypatch):
    monkeypatch.setattr(main.get_settings(), 'admin_username', '')
    assert client.post('/api/auth/login', json={
        'identifier': 'admin', 'password': 'local_test_only_password_12345'
    }).status_code == 401
    assert client.post('/api/auth/login', json={
        'identifier': 'owner@example.test', 'password': 'local_test_only_password_12345'
    }).status_code == 200
