import pytest
from app import create_app
from config import Config

class TestConfig(Config):
    TESTING = True
    WTF_CSRF_ENABLED = False

@pytest.fixture
def app():
    app = create_app(TestConfig)
    return app

@pytest.fixture
def client(app):
    return app.test_client()

def test_security_headers_in_test_mode(client):
    """Verify that Content-Security-Policy, X-Content-Type-Options, and X-Frame-Options are present in testing."""
    response = client.get('/')
    assert response.status_code == 200
    
    # Assert headers set by Talisman
    headers = response.headers
    assert 'Content-Security-Policy' in headers
    assert headers.get('X-Content-Type-Options') == 'nosniff'
    assert headers.get('X-Frame-Options') == 'SAMEORIGIN'
    
    # In test mode, Strict-Transport-Security must be absent (as force_https is disabled for HTTP dev/test)
    assert 'Strict-Transport-Security' not in headers

def test_hsts_and_https_redirect_in_prod_mode():
    """Verify that HSTS (Strict-Transport-Security) is enabled when debug and testing are False."""
    class ProdConfig(Config):
        TESTING = False
        DEBUG = False
        
    app_prod = create_app(ProdConfig)
    client_prod = app_prod.test_client()
    
    # Send a request over HTTPS (to inspect headers returned, as HTTP redirects to HTTPS)
    response = client_prod.get('/', base_url='https://localhost')
    assert 'Strict-Transport-Security' in response.headers
