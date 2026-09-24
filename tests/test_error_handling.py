import pytest
from app import create_app
from config import Config

class TestConfig(Config):
    TESTING = True
    WTF_CSRF_ENABLED = False

@pytest.fixture
def app():
    app = create_app(TestConfig)
    
    # Register a test route that triggers an unhandled exception containing PHI
    @app.route('/trigger-500-unhandled')
    def trigger_500():
        raise ValueError("Sensitive clinical PHI: Patient John Doe has stage 3 hypertension")
        
    return app

@pytest.fixture
def client(app):
    return app.test_client()

def test_unhandled_exception_sanitized_500(client):
    """Verify that unhandled exceptions do not leak tracebacks or PHI details in the response."""
    response = client.get('/trigger-500-unhandled')
    assert response.status_code == 500
    
    # Assert that the response contains the static error page and NOT the traceback details
    assert b"500" in response.data
    assert b"Internal Server Error" in response.data
    
    # Assert that the sensitive clinical info from the exception is completely absent
    assert b"John Doe" not in response.data
    assert b"stage 3 hypertension" not in response.data
    assert b"ValueError" not in response.data
    assert b"traceback" not in response.data
