import pytest
import os
import sys

def test_secret_key_required_in_non_testing(monkeypatch):
    """Verify that RuntimeError is raised when SECRET_KEY is missing in non-testing environments."""
    # Mock os.environ.get to return None for SECRET_KEY safely without recursion
    original_get = os.environ.get
    monkeypatch.setattr(os.environ, "get", lambda key, default=None: None if key == 'SECRET_KEY' else original_get(key, default))
    
    # Mock sys.modules to simulate that pytest is not loaded
    original_modules = sys.modules.copy()
    for k in list(sys.modules.keys()):
        if 'pytest' in k:
            del sys.modules[k]
            
    # Mock FLASK_ENV to be production
    monkeypatch.setenv('FLASK_ENV', 'production')
    
    # Remove config from sys.modules if already imported by previous tests
    sys.modules.pop('config', None)
    
    try:
        # We expect a RuntimeError to be raised when config is imported
        with pytest.raises(RuntimeError, match="SECRET_KEY environment variable must be set"):
            import config
    finally:
        # Restore sys.modules
        sys.modules.clear()
        sys.modules.update(original_modules)
