import os
import sys
from sqlalchemy.types import TypeDecorator, Text
from cryptography.fernet import Fernet
from flask import current_app

class EncryptedText(TypeDecorator):
    """A custom SQLAlchemy TypeDecorator that encrypts text using Fernet.
    It automatically decrypts values when retrieved from the DB, and encrypts
    them when saved.
    """
    impl = Text
    cache_ok = True

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._fernet = None

    @property
    def fernet(self):
        if self._fernet is None:
            key = None
            try:
                if current_app:
                    key = current_app.config.get('FIELD_ENCRYPTION_KEY')
            except RuntimeError:
                pass
            
            if not key:
                key = os.environ.get('FIELD_ENCRYPTION_KEY')
                
            if not key:
                _flask_env = os.environ.get('FLASK_ENV', '').lower()
                _is_testing = 'pytest' in sys.modules or _flask_env == 'testing'
                if _is_testing:
                    key = 'h_G-L7B0l38yK6qf3vS2Hh782wR4-r85kC-v_1E4-j0='
                else:
                    raise RuntimeError("FIELD_ENCRYPTION_KEY environment variable/configuration is missing!")
            
            self._fernet = Fernet(key.encode() if isinstance(key, str) else key)
        return self._fernet

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        encrypted_bytes = self.fernet.encrypt(value.encode('utf-8'))
        return encrypted_bytes.decode('utf-8')

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        try:
            decrypted_bytes = self.fernet.decrypt(value.encode('utf-8'))
            return decrypted_bytes.decode('utf-8')
        except Exception:
            return value
