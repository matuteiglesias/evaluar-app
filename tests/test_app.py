# tests/test_app.py
import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import pytest
from main import create_app
from flask import url_for
# Mockresponse
class MockResponse:
    def __init__(self, json_data, status_code):
        self.json_data = json_data
        self.status_code = status_code

    def json(self):
        return self.json_data


@pytest.fixture
def client():
    app = create_app()
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client

# # Environment configuration should be done outside of create_app for global access
# GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
# GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
# GOOGLE_DISCOVERY_URL = "https://accounts.google.com/.well-known/openid-configuration"


@pytest.fixture(autouse=True)
def set_env_vars():
    os.environ['GOOGLE_CLIENT_ID'] = os.getenv("GOOGLE_CLIENT_ID")
    os.environ['GOOGLE_CLIENT_SECRET'] = os.getenv("GOOGLE_CLIENT_SECRET")

def test_health(client):
    response = client.get('/health')
    assert response.status_code == 200
    assert response.json == {"status": "up"}


# 1. Test User Authentication Flow
def test_login_redirect(client):
    response = client.get('/login')
    assert response.status_code == 302
    # assert "accounts.google.com" in response.location  # This checks if redirection to Google's OAuth page occurs

def test_callback_handling(client, mocker):
    # Mock `requests.post` to simulate Google's response for token exchange
    mocker.patch('requests.post', return_value=MockResponse({
        'access_token': 'fake_access_token',
        'refresh_token': 'fake_refresh_token',
        'token_type': 'Bearer',
        'expires_in': 3600,
    }, 200))
    
    # Mock `requests.get` to simulate Google's UserInfo response
    mocker.patch('requests.get', return_value=MockResponse({
        'sub': '1234567890',
        'email': 'user@example.com',
        'email_verified': True,
        'name': 'Mock User',
        'picture': 'https://example.com/photo.jpg',
    }, 200))

    # response = client.get('/login/callback?code=fake_auth_code') ## need to fix this

    # assert response.status_code == 302
    # assert url_for('index') in response.location  # This checks if user is redirected to the index page after authentication


# 2. Test Exercise Content Retrieval
def test_get_exercises(client):
    response = client.get('/get_exercises')
    assert response.status_code == 200
    assert isinstance(response.json, list)  # This checks if a list of exercises is returned

def test_view_exercise(client):
    response = client.get('/exercises/TerrenodeTrampas.txt')
    assert response.status_code == 200
    # fix this
    # assert "Exercise content" in response.data.decode('utf-8')  # Replace "Exercise content" with actual expected content


# 3. Test Submission and Feedback
def test_submit_answer(client):
    with client.session_transaction() as sess:
        sess['user'] = {'id_': '123', 'name': 'Test User', 'email': 'test@example.com'}

    response = client.post('/submit_answer', data={'exercise_id': 'sample_exercise', 'response': 'Test answer'})
    assert response.status_code == 200
    # assert "Your feedback" in response.data.decode('utf-8')  # Replace "Your feedback" with actual expected feedback content


# 4. Logout and Session Clearing
def test_logout(client):
    with client.session_transaction() as sess:
        sess['user'] = {'id_': '123', 'name': 'Test User'}

    response = client.get('/logout')
    assert response.status_code == 302
    assert url_for('index') in response.location
    with client.session_transaction() as sess:
        assert 'user' not in sess  # This checks if the session is cleared

