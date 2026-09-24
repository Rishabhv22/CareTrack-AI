import pytest
from sqlalchemy import text
from app import create_app, db
from app.models.user import User
from app.models.patient import Patient
from app.models.doctor import Doctor
from app.models.journal import JournalEntry
from app.models.recommendation import DoctorNote
from app.models.daily_log import DailyHealthLog
from config import Config

class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    WTF_CSRF_ENABLED = False
    FIELD_ENCRYPTION_KEY = 'h_G-L7B0l38yK6qf3vS2Hh782wR4-r85kC-v_1E4-j0='

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

def test_field_level_encryption_raw_storage(app):
    """Verify that ORM automatically encrypts sensitive fields, and raw SQL queries return ciphertext."""
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
        
        plaintext_allergies = "Severe peanut allergy and penicillin intolerance."
        plaintext_other_conds = "Mild asthma."
        plaintext_family_hist = "Father had hypertension."
        
        patient = Patient(
            user=user_pat,
            name='Encrypted Patient',
            age=45,
            gender='Female',
            height=160.0,
            weight=65.0,
            primary_condition='Type 2 Diabetes',
            other_conditions=plaintext_other_conds,
            allergies=plaintext_allergies,
            family_history=plaintext_family_hist
        )
        db.session.add(patient)
        db.session.flush()

        # Create staged journal entry
        import datetime
        plaintext_journal = "Today I felt a sharp pain in my chest after running for 20 minutes."
        journal = JournalEntry(
            patient_id=patient.id,
            entry_date=datetime.date.today(),
            journal_text=plaintext_journal
        )
        db.session.add(journal)

        # Create Doctor Note
        plaintext_note = "Patient shows symptoms of mild wheezing, advised to keep inhaler nearby."
        note = DoctorNote(
            patient_id=patient.id,
            doctor_id=doc.id,
            note_text=plaintext_note
        )
        db.session.add(note)

        # Create DailyHealthLog symptoms
        plaintext_symptoms = "Shortness of breath, chest tightness."
        log = DailyHealthLog(
            patient_id=patient.id,
            log_date=datetime.date.today(),
            symptoms=plaintext_symptoms
        )
        db.session.add(log)
        db.session.commit()
        
        patient_id = patient.id
        journal_id = journal.id
        note_id = note.id
        log_id = log.id

    # 1. Verify transparent decryption via ORM queries
    with app.app_context():
        p_orm = db.session.get(Patient, patient_id)
        assert p_orm.allergies == plaintext_allergies
        assert p_orm.other_conditions == plaintext_other_conds
        assert p_orm.family_history == plaintext_family_hist
        
        j_orm = db.session.get(JournalEntry, journal_id)
        assert j_orm.journal_text == plaintext_journal
        
        n_orm = db.session.get(DoctorNote, note_id)
        assert n_orm.note_text == plaintext_note

        l_orm = db.session.get(DailyHealthLog, log_id)
        assert l_orm.symptoms == plaintext_symptoms

    # 2. Verify raw SQL select returns encrypted ciphertext (not plaintext)
    with app.app_context():
        # Query patient table directly via raw SQL
        p_raw = db.session.execute(text(f"SELECT allergies, other_conditions, family_history FROM patients WHERE id = '{patient_id}'")).fetchone()
        assert p_raw is not None
        assert plaintext_allergies not in p_raw[0]
        assert plaintext_other_conds not in p_raw[1]
        assert plaintext_family_hist not in p_raw[2]
        
        # Query journal entries table directly
        j_raw = db.session.execute(text(f"SELECT journal_text FROM journal_entries WHERE id = '{journal_id}'")).fetchone()
        assert j_raw is not None
        assert plaintext_journal not in j_raw[0]

        # Query doctor notes table directly
        n_raw = db.session.execute(text(f"SELECT note_text FROM doctor_notes WHERE id = '{note_id}'")).fetchone()
        assert n_raw is not None
        assert plaintext_note not in n_raw[0]

        # Query daily logs table directly
        l_raw = db.session.execute(text(f"SELECT symptoms FROM daily_health_logs WHERE id = '{log_id}'")).fetchone()
        assert l_raw is not None
        assert plaintext_symptoms not in l_raw[0]
