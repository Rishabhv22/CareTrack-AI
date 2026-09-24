import pytest
from app import create_app, db
from app.models.user import User
from app.models.patient import Patient
from app.models.doctor import Doctor
from app.models.recommendation import AuditLog
from config import Config

class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    WTF_CSRF_ENABLED = False

@pytest.fixture
def app():
    app = create_app(TestConfig)
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()

@pytest.fixture
def client(app):
    return app.test_client()

def test_password_length_restriction(client):
    """Verify that registration fails if the password is under 10 characters."""
    response = client.post('/auth/register', data={
        'email': 'new_patient@example.com',
        'password': 'short1',
        'confirm_password': 'short1',
        'role': 'PATIENT'
    }, follow_redirects=True)
    assert b'Password must be at least 10 characters long' in response.data

def test_password_complexity_requirement(client):
    """Verify that registration fails if the password lacks digits or letters."""
    # 1. No digits
    r1 = client.post('/auth/register', data={
        'email': 'new_patient@example.com',
        'password': 'lettersletters',
        'confirm_password': 'lettersletters',
        'role': 'PATIENT'
    }, follow_redirects=True)
    assert b'Password must contain at least one letter and one number' in r1.data

    # 2. No letters
    r2 = client.post('/auth/register', data={
        'email': 'new_patient@example.com',
        'password': '1234567890123',
        'confirm_password': '1234567890123',
        'role': 'PATIENT'
    }, follow_redirects=True)
    assert b'Password must contain at least one letter and one number' in r2.data

def test_login_rate_limiting_lockout(client, app):
    """Verify that 5 failed attempts locks out the user or IP for 15 minutes."""
    with app.app_context():
        # Create a patient user
        user = User(email='ratelimit@example.com', role='PATIENT')
        user.set_password('CorrectPassword123')
        db.session.add(user)
        # Also need a patient profile
        patient = Patient(user=user, name='Rate Limit Patient', age=30, gender='Male', height=170.0, weight=70.0, primary_condition='Hypertension')
        db.session.add(patient)
        db.session.commit()

    # Try logging in with incorrect credentials 5 times
    for _ in range(5):
        response = client.post('/auth/login', data={
            'email': 'ratelimit@example.com',
            'password': 'wrongpassword'
        }, follow_redirects=True)
        assert b'Invalid email or password' in response.data

    # The 6th attempt (even with correct password) should be locked out
    response_locked = client.post('/auth/login', data={
        'email': 'ratelimit@example.com',
        'password': 'CorrectPassword123'
    }, follow_redirects=True)
    assert b'Too many failed login attempts. Please try again in 15 minutes.' in response_locked.data

def test_clinical_record_view_creates_audit_log(client, app):
    """Verify that viewing a patient's detail page logs an audit entry with patient_id."""
    with app.app_context():
        user_doc = User(email='clinician@example.com', role='DOCTOR')
        user_doc.set_password('Password123')
        db.session.add(user_doc)
        doc = Doctor(user=user_doc, name='Clinician One', clinic_name='Clinic One')
        db.session.add(doc)

        user_pat = User(email='patient@example.com', role='PATIENT')
        user_pat.set_password('Password123')
        db.session.add(user_pat)
        patient = Patient(user=user_pat, name='Audited Patient', age=45, gender='Female', height=160.0, weight=65.0, primary_condition='Type 2 Diabetes')
        patient.doctors.append(doc)
        db.session.add(patient)
        db.session.commit()
        patient_id = patient.id
        doc_user_id = user_doc.id

    # Log in as Doctor
    client.post('/auth/login', data={'email': 'clinician@example.com', 'password': 'Password123'})

    # View patient details
    client.get(f'/doctor/patient/{patient_id}')

    # Verify that AuditLog entry was created
    with app.app_context():
        log = AuditLog.query.filter_by(action='VIEW_PATIENT_DETAIL').first()
        assert log is not None
        assert log.user_id == doc_user_id
        assert log.patient_id == patient_id

def test_login_session_is_permanent(client, app):
    """Verify that after logging in, the session is marked permanent."""
    with app.app_context():
        user = User(email='permanent@example.com', role='PATIENT')
        user.set_password('CorrectPassword123')
        db.session.add(user)
        patient = Patient(user=user, name='Permanent Patient', age=30, gender='Male', height=170.0, weight=70.0, primary_condition='Hypertension')
        db.session.add(patient)
        db.session.commit()

    # Log in and check session transaction
    client.post('/auth/login', data={
        'email': 'permanent@example.com',
        'password': 'CorrectPassword123'
    })
    
    with client.session_transaction() as sess:
        assert sess.permanent is True
