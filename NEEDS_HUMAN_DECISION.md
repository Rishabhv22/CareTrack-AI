# Human Decisions Required — CareTrack AI Hardening

This document lists architectural, legal, policy, and infrastructure decisions that must be resolved by human coordinators (compliance officers, database administrators, security teams, legal counsel) before CareTrack AI can be safely deployed in a pilot study or production setting.

---

## 🔒 Phase 1: Secrets & Environment Hygiene

### 1. Production Secrets Management
- **Decision Required:** How will the production `SECRET_KEY`, `GEMINI_API_KEY`, and database credentials be injected in staging and production?
- **Options:**
  - Inject via environment variables on the hosting platform (e.g. AWS Elastic Beanstalk, Heroku, Docker).
  - Use a dedicated secrets manager service (e.g. AWS Secrets Manager, Google Secret Manager, HashiCorp Vault).
- **Current Status:** Enforced hard crash at startup if `SECRET_KEY` is not set in non-testing environments.

### 2. Session Timeout Policy
- **Decision Required:** What is the maximum inactive session timeout permitted for doctors and patients?
- **Context:**
  - Currently set to **1 day** (`PERMANENT_SESSION_LIFETIME = timedelta(days=1)`) with `HttpOnly`, `SameSite=Lax`, and `Secure` (dynamic for dev vs prod) configurations.
  - Clinical systems typically require shorter timeout durations (e.g., 15 to 30 minutes of inactivity) on shared hospital workstations to prevent unauthorized viewing.
- **Action Needed:** Compliance team must approve or adjust the session timeout duration.

### 3. Tesseract OCR Engine Hosting
- **Decision Required:** Ensure the production server infrastructure installs and configures the Tesseract OCR binary package.
- **Action Needed:** Infrastructure team must verify that the target OS has Tesseract installed at `/usr/bin/tesseract` or configure `TESSERACT_PATH` in the system environment.

---

## 💾 Phase 3: Database & Data Protection

### 4. Patient PHI Data Retention & Deletion Policy
- **Decision Required:** How long should historical wearable data, daily logs, and AI summaries be stored?
- **Context:**
  - HIPAA and local state laws often dictate minimum retention periods for clinical and patient medical records (e.g., 6 to 10 years).
  - Patients may request deletion of their account under GDPR/CCPA. We must determine if and how we purge or anonymize clinical records (e.g., separating direct PII identifiers from historical biometric averages).
- **Action Needed:** Legal and compliance officers must establish the data retention and purge schedules.

### 5. Production PostgreSQL Encrypted Volume Storage
- **Decision Required:** Ensure the cloud provider's PostgreSQL hosting database uses KMS/AWS KMS encryption-at-rest.
- **Action Needed:** Infrastructure engineer must verify storage volume encryption is enabled on the managed database instance.

---

## 🔐 Phase 4: Auth Strengthening

### 6. Hospital Password Complexity Policy Alignment
- **Decision Required:** Review the implemented password validation rule (minimum 10 characters, at least one letter and one number) for alignment with institutional guidelines.
- **Context:**
  - HIPAA requirements and hospital corporate policies often specify stricter rules, such as mandatory uppercase, lowercase, and special character checks, or periodic password rotations (e.g. every 90 days).
- **Action Needed:** Security team must confirm if the 10+ alphanumeric password standard is sufficient or specify adjustments.

### 7. Brute-Force Lockout Action & Alerting
- **Decision Required:** Approve the threshold for brute-force lockouts and determine administrative override protocols.
- **Context:**
  - Currently, 5 failed attempts in 15 minutes restricts access per IP/account.
  - When locked out, should system administrators receive an alert?
  - What is the self-service reset or unlock procedure (e.g., email-based token, or mandatory calling of the clinical helpdesk)?
- **Action Needed:** Incident response and support operations must define the unlock workflow.

---

## 🏥 Phase 5: Clinical Safety Gates

### 8. AI/ML Acknowledgment Liability & Audits
- **Decision Required:** Establish the legal framework and liability policy for doctor acknowledgment of AI-generated summaries and ML analytics.
- **Context:**
  - When a clinician clicks "Verify & Acknowledge", we record this event in the `AuditLog` table.
  - Legal counsel must determine if this signature transfers responsibility/liability entirely to the clinician, or if the manufacturer/platform retains product liability for algorithm hallucinations or prediction errors.
- **Action Needed:** Clinical Risk Management and Legal Counsel must draft patient consent forms and doctor Terms of Use to clearly define limits of liability.

### 9. Retention of Unverified AI Summaries
- **Decision Required:** Determine the lifecycle of unverified/unacknowledged AI summaries.
- **Context:**
  - If a doctor does not review or acknowledge an AI Patient Progress Summary, should it remain permanently visible on the dashboard?
  - Should it automatically expire, archive, or lock after a set period (e.g. 14 days) to prevent stale or unverified clinical opinions from influencing care?
- **Action Needed:** Clinical Advisory Board must establish the visibility threshold and auto-expiry schedules.

---

## 🐞 Bug Fix Passes

### 10. Default Safety Fallback for Missing OCR Parameter Confidence
- **Decision Required:** Review and approve the fallback security threshold for parameters that have no staged OCR results in the database (e.g., manually entered parameters or modified parameter names).
- **Context:**
  - In `reports.py`, if a parameter is submitted that was not part of the initial OCR stage, we assign it a default confidence of `0.0`.
  - This forces the system to trigger the "low confidence" validation gate, requiring the user to explicitly confirm it is correct before saving.
- **Action Needed:** Confirm that this default-fail behavior is desired for manual modifications or if manual entries should bypass OCR gates.

---

## 🔒 Phase 6: Data Protection

### 11. Infrastructure-Level Encryption for Numeric PHI and Biometrics
- **Decision Required:** Review the fields flagged as relying on infrastructure-level database encryption rather than application-level encryption.
- **Context:**
  - Database columns such as biometric measurements (e.g., `weight`, `blood_glucose`, `systolic_bp`, `diastolic_bp`, `heart_rate`) and timestamps must not be encrypted at the application level.
  - This is because SQL queries filter, order, and aggregate them for continuous trend rendering. Application-level encryption would break all SQL querying/indexing capabilities for these metrics.
  - Therefore, we must rely on database/infrastructure-level storage volume encryption (e.g., AWS EBS volume encryption, or SQLite/SQLCipher filesystem encryption) to protect this data.
- **Action Needed:** Infrastructure engineer and security compliance officer must confirm that the production PostgreSQL server and all block storage volumes use cloud KMS encryption-at-rest.





