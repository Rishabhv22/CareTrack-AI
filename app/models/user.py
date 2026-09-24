import uuid
from datetime import datetime
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from app.extensions import db

class User(db.Model, UserMixin):
    __tablename__ = 'users'
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    username = db.Column(db.String(64), unique=True, nullable=True, index=True)
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(20), nullable=False, default='PATIENT') # 'PATIENT', 'DOCTOR', 'ADMIN'
    is_active_user = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    patient_profile = db.relationship('Patient', back_populates='user', uselist=False, cascade="all, delete-orphan")
    doctor_profile = db.relationship('Doctor', back_populates='user', uselist=False, cascade="all, delete-orphan")
    notifications = db.relationship('Notification', back_populates='user', cascade="all, delete-orphan")
    audit_logs = db.relationship('AuditLog', back_populates='user', cascade="all, delete-orphan")
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
        
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
        
    @property
    def is_active(self):
        # Override Flask-Login is_active property to allow deactivating users
        return self.is_active_user

    def has_role(self, role):
        return self.role.upper() == role.upper()

    def __repr__(self):
        return f'<User {self.email} ({self.role})>'
