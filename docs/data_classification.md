# Data Classification & PHI Inventory

This document maps all fields in the CareTrack AI database that contain Protected Health Information (PHI) under HIPAA regulations. This inventory defines the scope for encryption-at-rest and field-level encryption policies in subsequent compliance phases.

---

## 🏷️ Classification Tiers

1. **Direct Identifiers (PII):** Data elements that explicitly identify a patient.
2. **Clinical PHI:** Clinical findings, diagnostics, prescriptions, and clinician assessments.
3. **Behavioral & Telemetry PHI:** Patient check-ins, diary entries, and wearable device sensors.

---

## 🗄️ Database Table & Field Inventory

### 1. `patients` Table
- **Classification:** PII / Clinical PHI
- **PHI Fields:**
  - `name` (Direct Identifier - PII)
  - `phone` (Direct Identifier - PII)
  - `age` (Demographics)
  - `gender` (Demographics)
  - `height`, `weight`, `bmi` (Biometrics)
  - `primary_condition`, `other_conditions` (Clinical Diagnoses)
  - `allergies`, `family_history` (Clinical History)

### 2. `daily_health_logs` Table
- **Classification:** Behavioral & Telemetry PHI
- **PHI Fields:**
  - `weight` (Telemetry)
  - `water_intake`, `calories`, `exercise_duration`, `sleep_hours` (Lifestyle / Adherence)
  - `blood_glucose` (Biometric)
  - `systolic_bp`, `diastolic_bp` (Biometric)
  - `mood`, `energy` (Symptom / Subjective state)
  - `symptoms` (Clinical symptoms)

### 3. `journal_entries` Table
- **Classification:** Behavioral & Clinical PHI (High Risk)
- **PHI Fields:**
  - `journal_text` (Free-text narrative containing raw medical disclosures)
  - `summary` (NLP-generated clinical status)
  - `extracted_symptoms`, `extracted_medications`, `extracted_diet_activity` (NLP extracted markers)

### 4. `medications` & `medication_logs` Tables
- **Classification:** Clinical PHI
- **PHI Fields:**
  - `name` (Prescribed drug name)
  - `dosage`, `frequency`, `timing`, `instructions` (Dosage regime details)
  - `status` (Adherence behavior logs)

### 5. `lab_results` Table
- **Classification:** Clinical PHI
- **PHI Fields:**
  - `parameter_name` (Diagnostic biomarkers)
  - `parameter_value` (Biomarker metrics)
  - `unit` (Biomarker metrics)
  - `normal_range` (Reference thresholds)

### 6. `doctor_notes` Table
- **Classification:** Clinical PHI (High Risk)
- **PHI Fields:**
  - `note_text` (Clinician clinical assessment narrative)

### 7. `clinical_insights` Table
- **Classification:** Clinical PHI
- **PHI Fields:**
  - `insight_text` (Aggregated trend details)

### 8. `ai_summaries` Table
- **Classification:** Clinical PHI
- **PHI Fields:**
  - `summary_text` (Synthesized clinical summary text)

### 9. `alerts` Table
- **Classification:** Clinical PHI
- **PHI Fields:**
  - `message` (Clinical alerts)
