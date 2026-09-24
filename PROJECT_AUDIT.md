# CareTrack AI — Project Audit Report

This report presents a thorough audit of the existing CareTrack AI codebase, identifying existing features, architecture, database design, ML pipelines, frontend layouts, bugs, security vulnerabilities, and gaps.

---

## 1. Existing Architecture & Project Structure
The application follows a standard monolithic Model-Service-Route structure in Flask:
*   **Launcher**: `app.py` serves as the primary entry point, executing the application factory `create_app()` from `app/__init__.py`.
*   **Configuration**: Settings are loaded in `config.py` from `.env` (via `load_dotenv`).
*   **Database layer**: Flask-SQLAlchemy manages model definitions in `app/models/`. `app/extensions.py` handles instantiation of `db`, `migrate`, `login_manager`, and `csrf`.
*   **Business Logic**: Segregated into `app/services/` for NLP parsing, OCR extraction, Jaccard search/RAG indexing, and adherence computations.
*   **Web routes**: Organised under `app/routes/` as Flask Blueprints for auth, patient, doctor, reports, medication, and AI helper utilities.
*   **Templates & Assets**: Traditional Jinja2 server-rendered views at `app/templates/` and styling/scripts at `app/static/`.

---

## 2. Feature-by-Feature Status Audit

| Feature Area | Current Implementation | Status | Notes / Gaps |
| :--- | :--- | :--- | :--- |
| **Authentication & RBAC** | Flask-Login with User profiles. Role check (PATIENT, DOCTOR, ADMIN) protects Blueprint endpoints. | **Working** | Role-based check needs to be universally enforced across all endpoints to avoid path traversal. |
| **Patient Profile** | Patient profile completion forms with auto-BMI calculator. | **Working** | BMI values are successfully stored in SQLite database. |
| **Daily Health Monitoring** | Log fields for weight, sleep, metrics (glucose, blood pressure), exercise, diet, mood, and journal. | **Working** | Limits check-in logs to one record per patient per day. |
| **Medication Tracker** | Doctors define medications; patients log taken/missed status. Adherence is calculated. | **Working** | Patient cannot edit prescribed medication, only mark daily status. |
| **OCR Report Analyzer** | PyMuPDF extracts text; Tesseract OCR handles scanned PDFs/images. Regex maps common values. | **Partial** | Missing **extraction confidence metrics** and visual warnings if OCR confidence is low. |
| **Historical Comparison** | Displays logs/biometrics. | **Missing** | No direct **Previous vs Latest report parameter comparison** timeline showing differences and percentage changes. |
| **Patient Journal NLP** | spaCy negations checks symptoms, logs medications/exercise, and sets warning flags. | **Working** | Successfully filters symptoms like "no pain" using basic spaCy rules. |
| **Clinical Insight Engine** | `insight_engine.py` processes daily logs and raises biometric/adherence alert flags. | **Working** | Biometric and compliance alerts are correctly created in SQLite. |
| **Care Adherence Score** | Custom weight calculation out of 100 based on meds, logs, exercise, and diet. | **Working** | Adherence scores are computed in real time by the compliance engine. |
| **Machine Learning** | Random Forest categorises progress (Improving/Stable/Deteriorating); K-Means groups adherence. | **Partial** | ML models are stored as `.joblib`. The training script `ml/train.py` needs to run automatically if model files are missing. |
| **Patient Timeline** | Linear log listings. | **Missing** | Gaps in rendering a visual timeline of diagnostic milestones, report uploads, notes, and AI summaries. |
| **AI Weekly Summary** | Gemini API is utilized via `google.generativeai` with a Markdown statistical fallback. | **Working** | Overwrites previous summaries when generating a new one instead of saving a **historical weekly log**. |
| **AI Assistant / RAG** | NumPy Jaccard similarity matching queries AHA/WHO guidelines. | **Working** | Currently a token-keyword matching RAG. Fallbacks execute if `GEMINI_API_KEY` is missing. |
| **Doctor Dashboard** | Metrics display, patient listing tables, filters by adherence/condition, and alert sidebar. | **Working** | AJAX alerts acknowledgement works. Needs modern responsive UI polishing. |
| **Doctor Notes & Audits** | Doctor patient note editor. Audit logs track registrations and logins. | **Working** | AuditLog database schemas are defined and tracked. |

---

## 3. Technical Audit & Security Concerns

### Security & Privacy
*   **Secrets Exposure**: Hardcoded fallback secret keys in `config.py` have been mitigated via a `RuntimeError` on production setups, but `.env` must never be checked into Git.
*   **Open Redirect**: Redirection in the `auth.login` method was open to path hijacking, but has been secured using a same-origin relative path check.
*   **RBAC Permissions**: Ensure doctors cannot retrieve patient dashboards, and patients are restricted from viewing unassigned clinician reports.

### Database Issues
*   **Lack of Migration Support**: Flask-Migrate is installed, but migrations need to be initialized (`flask db init`) to support schema evolution without database loss.
*   **Gaps in Schema**:
    *   No `confidence` column in the `lab_results` table to store OCR extraction quality.
    *   `AISummary` records do not support multiple weekly summary entries (old ones are deleted during `generate_patient_summary`).

### UI/UX Inconsistencies
*   **Dashboard Aesthetics**: The interface needs a modern health-tech redesign with consistent sidebars, card metrics, and dense data displays for clinicians.
*   **Alert Container A11y**: Screen readers need polite updates (`aria-live="polite"`) when alerts are pushed or resolved.

---

## 4. Key Gaps to Resolve (To achieve Capstone/SaaS MVP standards)
1.  **Add LabResult Confidence Column**: Support OCR confidence calculations and show warning banners if the confidence score is low.
2.  **Verify & Edit Extracted OCR Values**: Let users verify and override parameters before finalizing database storage.
3.  **Historical Laboratory Comparison**: Compare HbA1c, Cholesterol, and BP over time, showing changes and differences in a side-by-side view.
4.  **Patient Timeline**: A visual timeline combining diagnostic milestones, report uploads, symptoms, and summaries.
5.  **Multi-Week AI Summary History**: Save historical weekly summaries to database so doctors can trace progress week-by-week.
6.  **ML Pipeline Auto-Train & XGBoost Upgrade**: Auto-train model if `.joblib` files are missing, and integrate an XGBoost option if needed.
7.  **Responsive Dashboard UI Upgrade**: Redesign dashboards using modern layouts, progress rings, and consistent components.
