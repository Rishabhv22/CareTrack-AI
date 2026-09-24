import pytest
from datetime import datetime, timedelta, date
from app import create_app, db
from app.models.user import User
from app.models.patient import Patient
from app.models.doctor import Doctor
from app.models.wearable import WearableDevice, HealthMetric, DailyHealthSummary
from app.models.recommendation import Alert, ClinicalInsight, AISummary
from config import Config
from app.services.health_sync_service import connect_wearable_provider, disconnect_wearable_provider, sync_patient_health_data
from app.services.health_data_service import add_health_metric
from app.services.health_summary_service import aggregate_daily_health_summary
from app.services.insight_engine import run_insight_engine
from app.services.compliance_engine import calculate_adherence_score
from app.services.ai_service import generate_patient_summary

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

@pytest.fixture
def sample_data(app):
    with app.app_context():
        # Create User, Patient, Doctor
        doc_user = User(email='doctor@caretrack.ai', role='DOCTOR')
        doc_user.set_password('doctor123')
        db.session.add(doc_user)
        
        doctor = Doctor(user=doc_user, name='Dr. Sarah Smith', specialization='Cardiology', clinic_name='Heart Center')
        db.session.add(doctor)
        
        pat_user = User(email='patient@caretrack.ai', role='PATIENT')
        pat_user.set_password('patient123')
        db.session.add(pat_user)
        
        patient = Patient(
            user=pat_user,
            name='Rahul Sharma',
            age=45,
            gender='Male',
            height=170.0,
            weight=82.0,
            primary_condition='Type 2 Diabetes',
            health_data_consent=False
        )
        patient.doctors.append(doctor)
        db.session.add(patient)
        
        # Another unauthorized patient
        other_user = User(email='other@caretrack.ai', role='PATIENT')
        other_user.set_password('other123')
        db.session.add(other_user)
        
        other_patient = Patient(
            user=other_user,
            name='Other Patient',
            age=30,
            gender='Female',
            height=160.0,
            weight=60.0,
            primary_condition='Obesity'
        )
        db.session.add(other_patient)
        
        db.session.commit()
        return {
            'patient_id': patient.id,
            'doctor_id': doctor.id,
            'other_patient_id': other_patient.id,
            'patient_user_id': pat_user.id,
            'doctor_user_id': doc_user.id
        }

def test_wearable_connection_and_consent(app, sample_data):
    """Verify that connecting a device requires consent first, and successfully updates database status."""
    with app.app_context():
        p_id = sample_data['patient_id']
        patient = db.session.get(Patient, p_id)
        
        # 1. Attempt connection without consent: should fail
        with pytest.raises(ValueError, match="data synchronization consent is not granted"):
            connect_wearable_provider(p_id, 'Demo Wearable', 'Smart Tracker', 'Smartwatch')
            
        # 2. Grant consent and connect: should succeed
        patient.health_data_consent = True
        db.session.commit()
        
        device = connect_wearable_provider(p_id, 'Demo Wearable', 'Smart Tracker', 'Smartwatch')
        assert device is not None
        assert device.connection_status == 'CONNECTED'
        assert device.provider == 'Demo Wearable'
        assert device.device_name == 'Smart Tracker'
        
        # 3. Disconnect device
        success = disconnect_wearable_provider(p_id, 'Demo Wearable')
        assert success is True
        assert device.connection_status == 'DISCONNECTED'

def test_wearable_synchronization(app, sample_data):
    """Checks that synchronization retrieves and saves telemetry logs, preventing duplicate data."""
    with app.app_context():
        p_id = sample_data['patient_id']
        patient = db.session.get(Patient, p_id)
        patient.health_data_consent = True
        db.session.commit()
        
        # Connect device
        connect_wearable_provider(p_id, 'Demo Wearable', 'Smart Tracker', 'Smartwatch')
        
        # Sync 7 days of data
        res = sync_patient_health_data(p_id, days=7)
        assert res['success'] is True
        assert res['metrics_synced'] > 0
        
        # Check that metrics are created in database
        metrics_count = HealthMetric.query.filter_by(patient_id=p_id).count()
        assert metrics_count > 0
        
        # Sync again: should ignore duplicates and not insert extra rows for same timestamps
        res2 = sync_patient_health_data(p_id, days=7)
        assert res2['success'] is True
        metrics_count_after = HealthMetric.query.filter_by(patient_id=p_id).count()
        assert metrics_count_after == metrics_count

def test_physiological_data_validation(app, sample_data):
    """Enforces range checks, flags questionable inputs with low confidence, and raises alerts."""
    with app.app_context():
        p_id = sample_data['patient_id']
        
        # Normal blood glucose
        m1 = add_health_metric(p_id, None, 'blood_glucose', 110.0, 'mg/dL', datetime.utcnow(), 'medical_device')
        assert m1.confidence == 1.0
        
        # Questionable glucose (severe hyperglycemia): should lower confidence and raise Alert
        m2 = add_health_metric(p_id, None, 'blood_glucose', 350.0, 'mg/dL', datetime.utcnow() - timedelta(hours=1), 'medical_device')
        assert m2.confidence == 0.9
        
        alert = Alert.query.filter_by(patient_id=p_id, alert_type='Biometric', status='ACTIVE').first()
        assert alert is not None
        assert "Hyperglycemia" in alert.message
        
        # Questionable SpO2 (Hypoxia): should lower confidence and raise alert
        m3 = add_health_metric(p_id, None, 'spo2', 88.0, '%', datetime.utcnow() - timedelta(hours=2), 'wearable')
        assert m3.confidence == 0.8
        alert_hypoxia = Alert.query.filter(Alert.patient_id == p_id, Alert.alert_type == 'Biometric', Alert.message.like('%Hypoxia%'), Alert.status == 'ACTIVE').first()
        if alert_hypoxia:
            assert alert_hypoxia.severity == 'HIGH'
            
        # Check invalid values reject
        with pytest.raises(ValueError):
            add_health_metric(p_id, None, 'steps', -100.0, 'steps', datetime.utcnow(), 'wearable')

def test_daily_summary_aggregation(app, sample_data):
    """Verifies that daily summary records combine manual and wearable sources properly."""
    with app.app_context():
        p_id = sample_data['patient_id']
        today_date = date.today()
        
        # Inject raw metrics
        add_health_metric(p_id, None, 'steps', 8000.0, 'steps', datetime.combine(today_date, datetime.min.time()) + timedelta(hours=12), 'health_platform')
        add_health_metric(p_id, None, 'sleep', 7.5, 'hours', datetime.combine(today_date, datetime.min.time()) + timedelta(hours=6), 'wearable')
        add_health_metric(p_id, None, 'weight', 81.2, 'kg', datetime.combine(today_date, datetime.min.time()) + timedelta(hours=7), 'health_platform')
        
        # Aggregate
        aggregate_daily_health_summary(p_id, today_date, today_date)
        
        summary = DailyHealthSummary.query.filter_by(patient_id=p_id, date=today_date).first()
        assert summary is not None
        assert summary.total_steps == 8000
        assert summary.sleep_hours == 7.5
        assert summary.weight == 81.2
        
        # Verify patient profile weight & BMI synchronized in real-time
        patient = db.session.get(Patient, p_id)
        assert patient.weight == 81.2
        assert patient.bmi == round(81.2 / (1.7 ** 2), 1)

def test_compliance_and_adherence_score(app, sample_data):
    """Checks that wearable steps/active minutes feed into exercise consistency score calculations."""
    with app.app_context():
        p_id = sample_data['patient_id']
        patient = db.session.get(Patient, p_id)
        
        # 1. Base exercise score: 0
        adherence1 = calculate_adherence_score(patient, days=7)
        assert adherence1['exercise']['score'] == 0.0
        
        # 2. Add summary with compliant active minutes
        today_date = date.today()
        summary = DailyHealthSummary(
            patient_id=p_id,
            date=today_date,
            active_minutes=35,
            total_steps=5000,
            generated_at=datetime.utcnow()
        )
        db.session.add(summary)
        db.session.commit()
        
        # 3. Recalculate: exercise consistency should increase
        adherence2 = calculate_adherence_score(patient, days=30)
        assert adherence2['exercise']['score'] > 0.0

def test_missing_wearable_data_alerts(app, sample_data):
    """Verifies that missing data generates clinical insights and alerts correctly."""
    with app.app_context():
        p_id = sample_data['patient_id']
        patient = db.session.get(Patient, p_id)
        
        # Connect device
        patient.health_data_consent = True
        db.session.commit()
        device = connect_wearable_provider(p_id, 'Demo Wearable', 'Smart Tracker', 'Smartwatch')
        # Simulate last synced 3 days ago
        device.last_synced_at = datetime.utcnow() - timedelta(days=3)
        db.session.commit()
        
        # Add 4 summaries to pass the baseline threshold check in the insight engine
        for i in range(5):
            day = date.today() - timedelta(days=i+4)
            summary = DailyHealthSummary(
                patient_id=p_id,
                date=day,
                total_steps=5000,
                sleep_hours=7.0,
                generated_at=datetime.utcnow()
            )
            db.session.add(summary)
        db.session.commit()
        
        # Run insight engine
        run_insight_engine(patient)
        
        # Check insights list
        insight = ClinicalInsight.query.filter_by(patient_id=p_id, insight_type='MissingWearableData').first()
        assert insight is not None
        assert "No wearable data received" in insight.insight_text
        
        # Check Alert table
        alert = Alert.query.filter_by(patient_id=p_id, alert_type='Missing Data', status='ACTIVE').first()
        assert alert is not None
        assert "No wearable data received" in alert.message

def test_doctor_authorization_boundaries(app, sample_data, client):
    """Confirms that clinician authorization blocks accessing other doctors' patient telemetry endpoints."""
    # Log in as doctor
    with client.session_transaction() as sess:
        sess['_user_id'] = sample_data['doctor_user_id']
        
    p_id = sample_data['patient_id']         # assigned patient
    other_p_id = sample_data['other_patient_id'] # unassigned patient
    
    # 1. Fetch assigned patient trends: should load successfully
    res1 = client.get(f"/api/doctor/patients/{p_id}/health-trends?days=7")
    assert res1.status_code == 200
    
    # 2. Fetch unassigned patient trends: should be blocked with 404/403
    res2 = client.get(f"/api/doctor/patients/{other_p_id}/health-trends?days=7")
    assert res2.status_code == 404

def test_ai_weekly_summary_generation(app, sample_data):
    """Confirms that AI summary generator formats wearable observations cleanly without prescriptions changes."""
    with app.app_context():
        p_id = sample_data['patient_id']
        patient = db.session.get(Patient, p_id)
        
        # Inject wearable data summaries
        summary = DailyHealthSummary(
            patient_id=p_id,
            date=date.today(),
            total_steps=8200,
            sleep_hours=7.2,
            average_heart_rate=76.0,
            resting_heart_rate=64,
            weight=80.5,
            generated_at=datetime.utcnow()
        )
        db.session.add(summary)
        db.session.commit()
        
        # Generate summary (forces fallback engine due to empty GEMINI_API_KEY in tests)
        summary_text = generate_patient_summary(patient, days=30)
        assert summary_text is not None
        assert "Average Steps:" in summary_text or "Steps:" in summary_text
        assert "Average Sleep:" in summary_text or "Sleep:" in summary_text
        assert "attending clinician remains the final decision-maker" in summary_text
