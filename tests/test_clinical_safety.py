import pytest
from app import create_app, db
from app.models.user import User
from app.models.patient import Patient
from app.models.doctor import Doctor
from app.models.recommendation import AISummary, Alert
from app.models.medical_report import MedicalReport, LabResult
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

def test_low_ocr_confidence_logic_gate(client, app):
    """Verify that low OCR confidence values must be explicitly confirmed to be saved."""
    with app.app_context():
        # Setup doctor & patient
        user_doc = User(email='doctor@example.com', role='DOCTOR')
        user_doc.set_password('Password123')
        db.session.add(user_doc)
        doc = Doctor(user=user_doc, name='Doctor One', clinic_name='Clinic One')
        db.session.add(doc)

        user_pat = User(email='patient@example.com', role='PATIENT')
        user_pat.set_password('Password123')
        db.session.add(user_pat)
        patient = Patient(user=user_pat, name='Audited Patient', age=45, gender='Female', height=160.0, weight=65.0, primary_condition='Type 2 Diabetes')
        patient.doctors.append(doc)
        db.session.add(patient)

        # Create report and a low-confidence lab result (80.0%)
        report = MedicalReport(patient=patient, file_name='report.pdf', file_path='report.pdf', uploaded_by_id=user_pat.id)
        db.session.add(report)
        db.session.flush()

        lab = LabResult(
            report_id=report.id,
            patient_id=patient.id,
            parameter_name='HbA1c',
            parameter_value=7.5,
            unit='%',
            normal_range='4.0 - 5.6',
            confidence=80.0
        )
        db.session.add(lab)
        db.session.commit()
        report_id = report.id

    # Log in as doctor
    client.post('/auth/login', data={'email': 'doctor@example.com', 'password': 'Password123'})

    # 1. Attempt review submission WITHOUT confirming
    r1 = client.post(f'/reports/review/{report_id}', data={
        'param_name[]': ['HbA1c'],
        'param_value[]': ['7.5'],
        'param_unit[]': ['%'],
        'param_range[]': ['4.0 - 5.6'],
        'param_confidence[]': ['80.0'],
        'test_date': '2026-08-25'
    }, follow_redirects=True)
    assert b"must be explicitly confirmed" in r1.data

    # 2. Submit WITH confirmation checked
    r2 = client.post(f'/reports/review/{report_id}', data={
        'param_name[]': ['HbA1c'],
        'param_value[]': ['7.5'],
        'param_unit[]': ['%'],
        'param_range[]': ['4.0 - 5.6'],
        'param_confidence[]': ['80.0'],
        'param_confirmed[]': ['HbA1c'],  # Confirmed parameter name
        'test_date': '2026-08-25'
    }, follow_redirects=True)
    assert b"must be explicitly confirmed" not in r2.data
    assert b"Report analysis reviewed and saved successfully!" in r2.data

def test_ai_ml_acknowledgment_routes(client, app):
    """Verify that doctor can acknowledge/verify AI summaries and ML predictions."""
    with app.app_context():
        user_doc = User(email='doctor@example.com', role='DOCTOR')
        user_doc.set_password('Password123')
        db.session.add(user_doc)
        doc = Doctor(user=user_doc, name='Doctor One', clinic_name='Clinic One')
        db.session.add(doc)

        user_pat = User(email='patient@example.com', role='PATIENT')
        user_pat.set_password('Password123')
        db.session.add(user_pat)
        patient = Patient(user=user_pat, name='Audited Patient', age=45, gender='Female', height=160.0, weight=65.0, primary_condition='Type 2 Diabetes')
        patient.doctors.append(doc)
        db.session.add(patient)

        import datetime
        summary = AISummary(patient=patient, summary_text='Test AI Summary', start_date=datetime.date.today(), end_date=datetime.date.today(), is_acknowledged=False)
        db.session.add(summary)
        db.session.commit()
        
        patient_id = patient.id
        summary_id = summary.id

    client.post('/auth/login', data={'email': 'doctor@example.com', 'password': 'Password123'})

    # 1. Acknowledge AI Summary
    res_summary = client.post(f'/doctor/ai-summary/acknowledge/{summary_id}')
    assert res_summary.status_code == 200
    assert res_summary.json['success'] is True

    # 2. Acknowledge ML Prediction
    res_ml = client.post(f'/doctor/patient/{patient_id}/ml/acknowledge')
    assert res_ml.status_code == 200
    assert res_ml.json['success'] is True

    # Verify state in DB
    with app.app_context():
        s = db.session.get(AISummary, summary_id)
        p = db.session.get(Patient, patient_id)
        assert s.is_acknowledged is True
        assert p.ml_acknowledged is True

def test_low_ocr_confidence_client_tamper_bypass(client, app):
    """Verify that tampering with the confidence value client-side is ignored and the gate still triggers."""
    with app.app_context():
        # Setup doctor & patient
        user_doc = User(email='doctor2@example.com', role='DOCTOR')
        user_doc.set_password('Password123')
        db.session.add(user_doc)
        doc = Doctor(user=user_doc, name='Doctor Two', clinic_name='Clinic Two')
        db.session.add(doc)

        user_pat = User(email='patient2@example.com', role='PATIENT')
        user_pat.set_password('Password123')
        db.session.add(user_pat)
        patient = Patient(user=user_pat, name='Audited Patient 2', age=45, gender='Female', height=160.0, weight=65.0, primary_condition='Type 2 Diabetes')
        patient.doctors.append(doc)
        db.session.add(patient)

        # Create report and a low-confidence lab result (80.0% staged on server)
        report = MedicalReport(patient=patient, file_name='report2.pdf', file_path='report2.pdf', uploaded_by_id=user_pat.id)
        db.session.add(report)
        db.session.flush()

        lab = LabResult(
            report_id=report.id,
            patient_id=patient.id,
            parameter_name='HbA1c',
            parameter_value=7.5,
            unit='%',
            normal_range='4.0 - 5.6',
            confidence=80.0
        )
        db.session.add(lab)
        db.session.commit()
        report_id = report.id

    # Log in as doctor
    client.post('/auth/login', data={'email': 'doctor2@example.com', 'password': 'Password123'})

    # Attempt to bypass by submitting high confidence (99.0%) in the form data
    # WITHOUT checking the confirmation checkbox
    response = client.post(f'/reports/review/{report_id}', data={
        'param_name[]': ['HbA1c'],
        'param_value[]': ['7.5'],
        'param_unit[]': ['%'],
        'param_range[]': ['4.0 - 5.6'],
        'param_confidence[]': ['99.0'],  # Client tampered confidence value
        'test_date': '2026-08-25'
    }, follow_redirects=True)

    # The backend must ignore 99.0, fetch 80.0, and block because no confirmation is checked
    assert b"must be explicitly confirmed" in response.data

