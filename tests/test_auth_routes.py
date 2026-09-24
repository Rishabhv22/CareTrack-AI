import pytest
from app import create_app, db
from app.models.user import User
from app.models.patient import Patient
from app.models.doctor import Doctor
from app.models.medication import Medication
from app.models.recommendation import Alert
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

def test_unauthenticated_dashboard_redirects(client):
    """(b) an unauthenticated request to /patient/dashboard redirects to login"""
    response = client.get('/patient/dashboard')
    assert response.status_code == 302
    assert '/auth/login' in response.headers['Location']

def test_login_open_redirect_blocked(client, app):
    """(c) the login open-redirect fix blocks an external next URL and redirects to dashboard"""
    with app.app_context():
        # Create a patient user
        user = User(email='test_patient@example.com', role='PATIENT')
        user.set_password('password123')
        db.session.add(user)
        # Also need a patient profile to avoid redirecting to create_profile
        patient = Patient(user=user, name='Test Patient', age=30, gender='Male', height=170.0, weight=70.0, primary_condition='Hypertension')
        db.session.add(patient)
        db.session.commit()

    # Try logging in with next pointing to an external domain
    response = client.post('/auth/login?next=https://malicious-external-domain.com', data={
        'email': 'test_patient@example.com',
        'password': 'password123'
    }, follow_redirects=False)

    # It should redirect to the default dashboard /patient/dashboard instead of the external URL
    assert response.status_code == 302
    assert '/patient/dashboard' in response.headers['Location']

def test_doctor_cannot_access_unowned_patient(client, app):
    """(a) a doctor cannot access another doctor's patient via /doctor/patient/<id>"""
    with app.app_context():
        # Create Doctor 1 and Doctor 2
        user_doc1 = User(email='doctor1@example.com', role='DOCTOR')
        user_doc1.set_password('password123')
        db.session.add(user_doc1)
        doc1 = Doctor(user=user_doc1, name='Doctor One', clinic_name='Clinic One')
        db.session.add(doc1)

        user_doc2 = User(email='doctor2@example.com', role='DOCTOR')
        user_doc2.set_password('password123')
        db.session.add(user_doc2)
        doc2 = Doctor(user=user_doc2, name='Doctor Two', clinic_name='Clinic Two')
        db.session.add(doc2)

        # Create Patient and assign to Doctor 2
        user_pat = User(email='patient@example.com', role='PATIENT')
        user_pat.set_password('password123')
        db.session.add(user_pat)
        patient = Patient(user=user_pat, name='Unowned Patient', age=45, gender='Female', height=160.0, weight=65.0, primary_condition='Type 2 Diabetes')
        patient.doctors.append(doc2)
        db.session.add(patient)

        db.session.commit()
        patient_id = patient.id

    # Log in as Doctor 1
    login_response = client.post('/auth/login', data={
        'email': 'doctor1@example.com',
        'password': 'password123'
    })
    assert login_response.status_code == 302

    # Attempt to view Patient 2 (owned by Doctor 2)
    response = client.get(f'/doctor/patient/{patient_id}')
    
    # Doctor 1 does not own this patient, so should be redirected to doctor.dashboard
    assert response.status_code == 302
    assert '/doctor/dashboard' in response.headers['Location']

def test_doctor_cannot_prescribe_unowned_patient(client, app):
    """Doctor 1 cannot prescribe to Patient 2 (owned by Doctor 2)"""
    with app.app_context():
        user_doc1 = User(email='doctor1@example.com', role='DOCTOR')
        user_doc1.set_password('password123')
        db.session.add(user_doc1)
        doc1 = Doctor(user=user_doc1, name='Doctor One', clinic_name='Clinic One')
        db.session.add(doc1)

        user_doc2 = User(email='doctor2@example.com', role='DOCTOR')
        user_doc2.set_password('password123')
        db.session.add(user_doc2)
        doc2 = Doctor(user=user_doc2, name='Doctor Two', clinic_name='Clinic Two')
        db.session.add(doc2)

        user_pat = User(email='patient@example.com', role='PATIENT')
        user_pat.set_password('password123')
        db.session.add(user_pat)
        patient = Patient(user=user_pat, name='Unowned Patient', age=45, gender='Female', height=160.0, weight=65.0, primary_condition='Type 2 Diabetes')
        patient.doctors.append(doc2)
        db.session.add(patient)
        db.session.commit()
        patient_id = patient.id

    client.post('/auth/login', data={'email': 'doctor1@example.com', 'password': 'password123'})
    response = client.post(f'/doctor/patient/{patient_id}/prescribe', data={
        'name': 'Metformin',
        'dosage': '500mg',
        'frequency': 'Once daily'
    })
    assert response.status_code == 404

def test_doctor_cannot_stop_prescription_unowned_patient(client, app):
    """Doctor 1 cannot stop a prescription belonging to Patient 2 (owned by Doctor 2)"""
    with app.app_context():
        user_doc1 = User(email='doctor1@example.com', role='DOCTOR')
        user_doc1.set_password('password123')
        db.session.add(user_doc1)
        doc1 = Doctor(user=user_doc1, name='Doctor One', clinic_name='Clinic One')
        db.session.add(doc1)

        user_doc2 = User(email='doctor2@example.com', role='DOCTOR')
        user_doc2.set_password('password123')
        db.session.add(user_doc2)
        doc2 = Doctor(user=user_doc2, name='Doctor Two', clinic_name='Clinic Two')
        db.session.add(doc2)

        user_pat = User(email='patient@example.com', role='PATIENT')
        user_pat.set_password('password123')
        db.session.add(user_pat)
        patient = Patient(user=user_pat, name='Unowned Patient', age=45, gender='Female', height=160.0, weight=65.0, primary_condition='Type 2 Diabetes')
        patient.doctors.append(doc2)
        db.session.add(patient)

        med = Medication(patient=patient, prescribed_by_id=doc2.id, name='Metformin', dosage='500mg', frequency='Once daily', is_active=True)
        db.session.add(med)
        db.session.commit()
        patient_id = patient.id
        med_id = med.id

    client.post('/auth/login', data={'email': 'doctor1@example.com', 'password': 'password123'})
    response = client.post(f'/doctor/patient/{patient_id}/prescribe/stop/{med_id}')
    assert response.status_code == 302
    assert '/doctor/dashboard' in response.headers['Location']

def test_doctor_cannot_add_note_unowned_patient(client, app):
    """Doctor 1 cannot add a clinician note to Patient 2 (owned by Doctor 2)"""
    with app.app_context():
        user_doc1 = User(email='doctor1@example.com', role='DOCTOR')
        user_doc1.set_password('password123')
        db.session.add(user_doc1)
        doc1 = Doctor(user=user_doc1, name='Doctor One', clinic_name='Clinic One')
        db.session.add(doc1)

        user_doc2 = User(email='doctor2@example.com', role='DOCTOR')
        user_doc2.set_password('password123')
        db.session.add(user_doc2)
        doc2 = Doctor(user=user_doc2, name='Doctor Two', clinic_name='Clinic Two')
        db.session.add(doc2)

        user_pat = User(email='patient@example.com', role='PATIENT')
        user_pat.set_password('password123')
        db.session.add(user_pat)
        patient = Patient(user=user_pat, name='Unowned Patient', age=45, gender='Female', height=160.0, weight=65.0, primary_condition='Type 2 Diabetes')
        patient.doctors.append(doc2)
        db.session.add(patient)
        db.session.commit()
        patient_id = patient.id

    client.post('/auth/login', data={'email': 'doctor1@example.com', 'password': 'password123'})
    response = client.post(f'/doctor/patient/{patient_id}/note', data={'note_text': 'Illegal Note'})
    assert response.status_code == 302
    assert '/doctor/dashboard' in response.headers['Location']

def test_doctor_cannot_resolve_alert_unowned_patient(client, app):
    """Doctor 1 cannot resolve an alert belonging to Patient 2 (owned by Doctor 2)"""
    with app.app_context():
        user_doc1 = User(email='doctor1@example.com', role='DOCTOR')
        user_doc1.set_password('password123')
        db.session.add(user_doc1)
        doc1 = Doctor(user=user_doc1, name='Doctor One', clinic_name='Clinic One')
        db.session.add(doc1)

        user_doc2 = User(email='doctor2@example.com', role='DOCTOR')
        user_doc2.set_password('password123')
        db.session.add(user_doc2)
        doc2 = Doctor(user=user_doc2, name='Doctor Two', clinic_name='Clinic Two')
        db.session.add(doc2)

        user_pat = User(email='patient@example.com', role='PATIENT')
        user_pat.set_password('password123')
        db.session.add(user_pat)
        patient = Patient(user=user_pat, name='Unowned Patient', age=45, gender='Female', height=160.0, weight=65.0, primary_condition='Type 2 Diabetes')
        patient.doctors.append(doc2)
        db.session.add(patient)

        alert = Alert(patient=patient, alert_type='Biometric', severity='MEDIUM', message='BP alert')
        db.session.add(alert)
        db.session.commit()
        alert_id = alert.id

    client.post('/auth/login', data={'email': 'doctor1@example.com', 'password': 'password123'})
    response = client.post(f'/doctor/alert/resolve/{alert_id}')
    assert response.status_code == 404

def test_doctor_cannot_access_unowned_patient_apis(client, app):
    """Doctor 1 cannot query API data for Patient 2 (owned by Doctor 2)"""
    with app.app_context():
        user_doc1 = User(email='doctor1@example.com', role='DOCTOR')
        user_doc1.set_password('password123')
        db.session.add(user_doc1)
        doc1 = Doctor(user=user_doc1, name='Doctor One', clinic_name='Clinic One')
        db.session.add(doc1)

        user_doc2 = User(email='doctor2@example.com', role='DOCTOR')
        user_doc2.set_password('password123')
        db.session.add(user_doc2)
        doc2 = Doctor(user=user_doc2, name='Doctor Two', clinic_name='Clinic Two')
        db.session.add(doc2)

        user_pat = User(email='patient@example.com', role='PATIENT')
        user_pat.set_password('password123')
        db.session.add(user_pat)
        patient = Patient(user=user_pat, name='Unowned Patient', age=45, gender='Female', height=160.0, weight=65.0, primary_condition='Type 2 Diabetes')
        patient.doctors.append(doc2)
        db.session.add(patient)
        db.session.commit()
        patient_id = patient.id

    client.post('/auth/login', data={'email': 'doctor1@example.com', 'password': 'password123'})
    
    r1 = client.get(f'/api/doctor/patients/{patient_id}/health-summary')
    assert r1.status_code == 404
    
    r2 = client.get(f'/api/doctor/patients/{patient_id}/health-trends')
    assert r2.status_code == 404
    
    r3 = client.get(f'/api/doctor/patients/{patient_id}/clinical-insights')
    assert r3.status_code == 404

def test_doctor_cannot_upload_review_reports_unowned_patient(client, app):
    """Doctor 1 cannot upload or review medical reports for Patient 2 (owned by Doctor 2)"""
    with app.app_context():
        user_doc1 = User(email='doctor1@example.com', role='DOCTOR')
        user_doc1.set_password('password123')
        db.session.add(user_doc1)
        doc1 = Doctor(user=user_doc1, name='Doctor One', clinic_name='Clinic One')
        db.session.add(doc1)

        user_doc2 = User(email='doctor2@example.com', role='DOCTOR')
        user_doc2.set_password('password123')
        db.session.add(user_doc2)
        doc2 = Doctor(user=user_doc2, name='Doctor Two', clinic_name='Clinic Two')
        db.session.add(doc2)

        user_pat = User(email='patient@example.com', role='PATIENT')
        user_pat.set_password('password123')
        db.session.add(user_pat)
        patient = Patient(user=user_pat, name='Unowned Patient', age=45, gender='Female', height=160.0, weight=65.0, primary_condition='Type 2 Diabetes')
        patient.doctors.append(doc2)
        db.session.add(patient)

        from app.models.medical_report import MedicalReport
        report = MedicalReport(patient=patient, file_name='report.pdf', file_path='report.pdf', uploaded_by_id=user_pat.id)
        db.session.add(report)
        db.session.commit()
        patient_id = patient.id
        report_id = report.id

    client.post('/auth/login', data={'email': 'doctor1@example.com', 'password': 'password123'})
    
    # 1. Upload GET attempt
    r1 = client.get(f'/reports/upload?patient_id={patient_id}')
    assert r1.status_code == 302
    assert '/doctor/dashboard' in r1.headers['Location']
    
    # 2. Review GET attempt
    r2 = client.get(f'/reports/review/{report_id}')
    assert r2.status_code == 302
    assert '/doctor/dashboard' in r2.headers['Location']

def test_patient_cannot_review_other_patient_report(client, app):
    """Patient 1 cannot view or review reports of Patient 2"""
    with app.app_context():
        user_pat1 = User(email='patient1@example.com', role='PATIENT')
        user_pat1.set_password('password123')
        db.session.add(user_pat1)
        patient1 = Patient(user=user_pat1, name='Patient One', age=45, gender='Female', height=160.0, weight=65.0, primary_condition='Type 2 Diabetes')
        db.session.add(patient1)

        user_pat2 = User(email='patient2@example.com', role='PATIENT')
        user_pat2.set_password('password123')
        db.session.add(user_pat2)
        patient2 = Patient(user=user_pat2, name='Patient Two', age=30, gender='Male', height=175.0, weight=75.0, primary_condition='Obesity')
        db.session.add(patient2)

        from app.models.medical_report import MedicalReport
        report = MedicalReport(patient=patient2, file_name='report.pdf', file_path='report.pdf', uploaded_by_id=user_pat2.id)
        db.session.add(report)
        db.session.commit()
        report_id = report.id

    client.post('/auth/login', data={'email': 'patient1@example.com', 'password': 'password123'})
    response = client.get(f'/reports/review/{report_id}')
    assert response.status_code == 302
    assert '/auth/login' in response.headers['Location'] or '/' in response.headers['Location']

def test_patient_cannot_log_adherence_other_patient_medication(client, app):
    """Patient 1 cannot submit medication log updates for Patient 2's prescriptions"""
    with app.app_context():
        user_pat1 = User(email='patient1@example.com', role='PATIENT')
        user_pat1.set_password('password123')
        db.session.add(user_pat1)
        patient1 = Patient(user=user_pat1, name='Patient One', age=45, gender='Female', height=160.0, weight=65.0, primary_condition='Type 2 Diabetes')
        db.session.add(patient1)

        user_pat2 = User(email='patient2@example.com', role='PATIENT')
        user_pat2.set_password('password123')
        db.session.add(user_pat2)
        patient2 = Patient(user=user_pat2, name='Patient Two', age=30, gender='Male', height=175.0, weight=75.0, primary_condition='Obesity')
        db.session.add(patient2)

        med = Medication(patient=patient2, prescribed_by_id=999, name='Metformin', dosage='500mg', frequency='Once daily', is_active=True)
        db.session.add(med)
        db.session.commit()
        med_id = med.id

    client.post('/auth/login', data={'email': 'patient1@example.com', 'password': 'password123'})
    response = client.post(f'/medication/log/{med_id}', json={'status': 'TAKEN'})
    assert response.status_code == 403

