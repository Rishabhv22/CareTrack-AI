import sys
import os
import random
from datetime import datetime, timedelta

# Add root folder to sys.path so we can import app modules
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app
from app.extensions import db
from app.models.user import User
from app.models.doctor import Doctor
from app.models.patient import Patient
from app.models.medication import Medication, MedicationLog
from app.models.daily_log import DailyHealthLog
from app.models.journal import JournalEntry
from app.models.recommendation import Alert, AISummary, AuditLog, DoctorNote
from app.models.medical_report import MedicalReport, LabResult

def seed_database():
    app = create_app()
    with app.app_context():
        print("Wiping existing database...")
        db.drop_all()
        db.create_all()
        
        print("Creating default Admin and Doctor users...")
        # Create Admin
        admin_user = User(email="admin@caretrack.ai", role="ADMIN")
        admin_user.set_password("admin123")
        db.session.add(admin_user)
        
        # Create Doctor
        doc_user = User(email="doctor@caretrack.ai", role="DOCTOR")
        doc_user.set_password("doctor123")
        db.session.add(doc_user)
        db.session.commit()
        
        doctor = Doctor(
            user_id=doc_user.id,
            name="Dr. Sarah Jenkins",
            specialization="Cardiology & Endocrinology",
            phone="+1 (555) 019-2834",
            clinic_name="Metro Chronic Care Center"
        )
        db.session.add(doctor)
        db.session.commit()
        
        # Conditions list
        conditions = [
            ("Type 2 Diabetes", "Metformin 500mg (Daily)", "Lantus Insulin 10 units (Bedtime)"),
            ("Hypertension", "Lisinopril 10mg (Morning)", "Amlodipine 5mg (Evening)"),
            ("Obesity & Metabolic Syndrome", "Semaglutide 0.5mg (Weekly)", None),
            ("High Cholesterol", "Atorvastatin 20mg (Night)", "Coenzyme Q10 100mg (Morning)")
        ]
        
        patient_names = [
            "John Doe", "Jane Smith", "Robert Johnson", "Emily Davis", "Michael Miller",
            "David Wilson", "Linda Taylor", "James Anderson", "Elizabeth Thomas", "William Jackson",
            "Patricia White", "Charles Harris", "Barbara Martin", "Matthew Thompson", "Susan Garcia",
            "Joseph Martinez", "Jessica Robinson", "Thomas Clark", "Sarah Rodriguez", "Nancy Lewis"
        ]
        
        print(f"Creating 20 patients with 90 days log history...")
        today = datetime.utcnow().date()
        
        for i, name in enumerate(patient_names):
            email = f"patient{i+1}@caretrack.ai"
            u = User(email=email, role="PATIENT")
            u.set_password("patient123")
            db.session.add(u)
            db.session.commit()
            
            # Select condition template
            cond_name, med1_name, med2_name = conditions[i % len(conditions)]
            
            # Care Adherence Archetype selector:
            # i % 3: 0 = High compliance (90% logs/meds), 1 = Struggling (60%), 2 = Low compliance (30%)
            archetype = i % 3
            
            p = Patient(
                user_id=u.id,
                name=name,
                age=random.randint(35, 75),
                gender=random.choice(["Male", "Female"]),
                phone=f"+1 (555) 011-20{i:02d}",
                primary_condition=cond_name,
                height=random.randint(155, 188),
                weight=random.randint(65, 115) + (20 if "Obesity" in cond_name else 0),
                smoking=random.choice(["Never", "Former", "Active"]),
                alcohol=random.choice(["None", "Occasional", "Frequent"]),
                activity_level=random.choice(["Sedentary", "Lightly Active", "Moderately Active"]),
                other_conditions="None" if i % 2 == 0 else "Mild Osteoarthritis",
                allergies="Penicillin" if i % 5 == 0 else "None",
                family_history="Type 2 Diabetes in mother" if i % 4 == 0 else "None"
            )
            # Associate patient with the doctor
            p.doctors.append(doctor)
            db.session.add(p)
            db.session.commit()
            
            # Add prescribed medications
            meds = []
            if med1_name:
                m1 = Medication(
                    patient_id=p.id,
                    name=med1_name.split(" (")[0],
                    dosage=med1_name.split(" (")[1].replace(")", ""),
                    frequency="Once daily",
                    instructions="Take with water before meals",
                    prescribed_by=doctor
                )
                db.session.add(m1)
                meds.append(m1)
            if med2_name:
                m2 = Medication(
                    patient_id=p.id,
                    name=med2_name.split(" (")[0],
                    dosage=med2_name.split(" (")[1].replace(")", ""),
                    frequency="Once daily",
                    instructions="Take before bed",
                    prescribed_by=doctor
                )
                db.session.add(m2)
                meds.append(m2)
            db.session.commit()
            
            # Generate logs for last 90 days
            start_date = today - timedelta(days=90)
            
            base_weight = p.weight
            base_glucose = 145 if "Diabetes" in cond_name else 95
            base_sbp = 142 if "Hypertension" in cond_name else 118
            base_dbp = 92 if "Hypertension" in cond_name else 76
            
            for day_idx in range(90):
                log_date = start_date + timedelta(days=day_idx)
                
                # Determine if they check in on this day based on compliance archetype
                if archetype == 0:
                    check_in = random.random() < 0.92
                    med_took = random.random() < 0.95
                elif archetype == 1:
                    check_in = random.random() < 0.65
                    med_took = random.random() < 0.70
                else:
                    check_in = random.random() < 0.35
                    med_took = random.random() < 0.40
                    
                if check_in:
                    # Weight drift based on compliance
                    drift = -0.05 if archetype == 0 else (0.05 if archetype == 2 else 0.0)
                    weight = round(base_weight + drift * day_idx + random.uniform(-0.5, 0.5), 1)
                    
                    # Glucose drift
                    glu_drift = -0.4 if archetype == 0 else (0.3 if archetype == 2 else 0.0)
                    glucose = round(base_glucose + glu_drift * day_idx + random.randint(-15, 15))
                    
                    # BP drift
                    bp_drift = -0.3 if archetype == 0 else (0.2 if archetype == 2 else 0.0)
                    sbp = round(base_sbp + bp_drift * day_idx + random.randint(-8, 8))
                    dbp = round(base_dbp + bp_drift * 0.6 * day_idx + random.randint(-5, 5))
                    
                    # Log daily entries
                    duration = random.choice([0, 20, 30, 45]) if med_took else 0
                    log = DailyHealthLog(
                        patient_id=p.id,
                        log_date=log_date,
                        weight=weight,
                        blood_glucose=glucose,
                        systolic_bp=sbp,
                        diastolic_bp=dbp,
                        exercise_duration=duration,
                        exercise_completed=True if duration > 0 else False,
                        diet_followed=random.choice([True, False]) if archetype > 0 else True,
                        medicine_taken=med_took,
                        sleep_hours=random.choice([6.0, 7.0, 7.5, 8.0])
                    )
                    db.session.add(log)
                    
                    # Create journal text & parse symptoms
                    symptoms_choices = ["None", "I feel slightly tired", "Had a minor headache", "A bit lightheaded"]
                    symptom_text = random.choice(symptoms_choices) if med_took else "Missed my medicine today and feel sore all over."
                    
                    # Parse using rule-based/spaCy
                    from app.services.nlp_service import analyze_journal
                    nlp_res = analyze_journal(symptom_text)
                    
                    journal = JournalEntry(
                        patient_id=p.id,
                        daily_log_id=log.id,
                        entry_date=log_date,
                        journal_text=symptom_text,
                        summary=nlp_res["summary"],
                        extracted_symptoms=", ".join(nlp_res["symptoms"]) if nlp_res["symptoms"] else "None",
                        extracted_medications=nlp_res["medications"],
                        extracted_diet_activity=nlp_res["diet_activity"],
                        concerning_flag=nlp_res["concerning_flag"]
                    )
                    db.session.add(journal)
                    
                    # Mark Medication Logs
                    for m in meds:
                        status = 'TAKEN' if med_took else 'MISSED'
                        mlog = MedicationLog(
                            patient_id=p.id,
                            medication_id=m.id,
                            log_date=log_date,
                            status=status
                        )
                        db.session.add(mlog)
                        
            # Insert medical lab reports
            # Create a Baseline report at Day 90 (start) and a follow-up report at Day 10
            for report_day_offset in [80, 15]:
                report_date = today - timedelta(days=report_day_offset)
                
                # Mock parameters values based on time/compliance
                # Improvement for archetype 0, decline/steady for archetype 2
                improvement_coeff = 0.85 if (archetype == 0 and report_day_offset == 15) else 1.0
                
                report = MedicalReport(
                    patient_id=p.id,
                    file_name="comprehensive_lab_panel.pdf" if report_day_offset == 80 else "routine_health_check_report.pdf",
                    file_path=f"reports/report_{p.id}_{report_day_offset}.pdf",
                    raw_text=(
                        f"Metro Health Labs\n"
                        f"Date: {report_date.strftime('%Y-%m-%d')}\n"
                        f"Fasting Blood Sugar: {round(base_glucose * improvement_coeff)} mg/dL\n"
                        f"HbA1c (Glycated Hemoglobin): {round(7.8 * improvement_coeff, 1)} %\n"
                        f"Total Cholesterol: {round(240 * improvement_coeff)} mg/dL\n"
                        f"BP: {round(base_sbp * improvement_coeff)}/{round(base_dbp * improvement_coeff)} mmHg"
                    ),
                    uploaded_at=datetime.combine(report_date, datetime.min.time()),
                    is_processed=True
                )
                db.session.add(report)
                db.session.commit()
                
                # Add parameters
                from app.services.report_analyzer import extract_parameters
                extracted_params = extract_parameters(report.raw_text)
                for ep in extracted_params:
                    lp = LabResult(
                        report_id=report.id,
                        patient_id=p.id,
                        parameter_name=ep['parameter_name'],
                        parameter_value=ep['parameter_value'],
                        unit=ep['unit'],
                        normal_range=ep['normal_range'],
                        test_date=report_date
                    )
                    db.session.add(lp)
                db.session.commit()
                
            # Add doctor notes
            note = DoctorNote(
                patient_id=p.id,
                doctor_id=doctor.id,
                note_text=f"First consultation done. Patient diagnosed with {cond_name}. Initiated prescriptions and lifestyle care-tracking. Strongly advised diet & regular logs."
            )
            db.session.add(note)
            db.session.commit()

        # Generate some alerts for the doctor panel
        print("Generating active sidebar alerts...")
        alert_patients = Patient.query.all()[:3]
        for ap in alert_patients:
            alert = Alert(
                patient_id=ap.id,
                alert_type="Biometric",
                severity="HIGH",
                message=f"Blood pressure readings exceeded safety range: 155/98 mmHg (Logged yesterday).",
                status="ACTIVE"
            )
            db.session.add(alert)
        db.session.commit()
        
        print("Database seeding completed successfully!")

if __name__ == '__main__':
    seed_database()
