import os
import sys
import platform
from datetime import timedelta
from pathlib import Path
from dotenv import load_dotenv

# Load env file from the base directory
basedir = Path(__file__).resolve().parent
load_dotenv(basedir / '.env')

class Config:
    # Fail loudly if SECRET_KEY is missing in non-testing environments
    _secret_key = os.environ.get('SECRET_KEY')
    _flask_env = os.environ.get('FLASK_ENV', '').lower()
    _is_testing = 'pytest' in sys.modules or _flask_env == 'testing'
    
    if not _secret_key:
        if not _is_testing:
            raise RuntimeError("SECRET_KEY environment variable must be set in all non-testing environments!")
        _secret_key = 'testing-fallback-key'
    SECRET_KEY = _secret_key
    
    # Fail loudly if FIELD_ENCRYPTION_KEY is missing in non-testing environments
    _field_encryption_key = os.environ.get('FIELD_ENCRYPTION_KEY')
    if not _field_encryption_key:
        if not _is_testing:
            raise RuntimeError("FIELD_ENCRYPTION_KEY environment variable must be set in all non-testing environments!")
        _field_encryption_key = 'h_G-L7B0l38yK6qf3vS2Hh782wR4-r85kC-v_1E4-j0='
    FIELD_ENCRYPTION_KEY = _field_encryption_key
    
    # Database
    db_url = os.environ.get('DATABASE_URL')
    if db_url and db_url.startswith("postgres://"):
        # Fix for Heroku PostgreSQL url configuration changes
        db_url = db_url.replace("postgres://", "postgresql://", 1)
    
    _db_uri = db_url or f"sqlite:///{basedir / 'instance' / 'caretrack.db'}"
    SQLALCHEMY_DATABASE_URI = _db_uri
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    if _db_uri.startswith("sqlite"):
        SQLALCHEMY_ENGINE_OPTIONS = {
            "connect_args": {"timeout": 30}
        }

    
    # Upload Folder config
    UPLOAD_FOLDER = os.environ.get('UPLOAD_FOLDER', 'uploads')
    # Make sure absolute path is resolved properly
    UPLOAD_FOLDER_PATH = basedir / UPLOAD_FOLDER
    
    # 16 MB max size
    MAX_CONTENT_LENGTH = int(os.environ.get('MAX_CONTENT_LENGTH', 16 * 1024 * 1024))
    
    # Tesseract path (OS-aware default fallback)
    if platform.system() == 'Windows':
        _default_tesseract = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
    else:
        _default_tesseract = '/usr/bin/tesseract'
    TESSERACT_PATH = os.environ.get('TESSERACT_PATH', _default_tesseract)
    
    # Session Cookie Security Policies
    SESSION_COOKIE_SECURE = os.environ.get('SESSION_COOKIE_SECURE', 'False' if _is_testing or os.environ.get('FLASK_DEBUG') == '1' else 'True').lower() == 'true'
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    PERMANENT_SESSION_LIFETIME = timedelta(days=1)
    
    # Gemini API
    GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY', '')
    
    # Allowed medical report formats
    ALLOWED_EXTENSIONS = {'pdf', 'png', 'jpg', 'jpeg'}

    @classmethod
    def init_app(cls, app):
        # Create uploads folder if it doesn't exist
        os.makedirs(cls.UPLOAD_FOLDER_PATH, exist_ok=True)
        # Create instance folder for SQLite database
        os.makedirs(basedir / 'instance', exist_ok=True)
