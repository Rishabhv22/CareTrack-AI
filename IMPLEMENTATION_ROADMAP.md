# CareTrack AI — Implementation Roadmap

This document outlines the step-by-step roadmap for upgrading CareTrack AI into a Capstone-level chronic care platform and a viable SaaS MVP foundation.

---

## Phase 1: Audit & Stabilize Project (Completed)
*   [x] Perform a complete codebase audit and identify bugs, gaps, and security issues.
*   [x] Add missing module imports (e.g. `re` in `ai_service.py`).
*   [x] Stabilize virtualenv, dependencies, and environment setup.
*   [x] Ensure tests execute and compile successfully.

---

## Phase 2: Fix Authentication, RBAC, and Database Schema
*   [ ] Initialize database migrations using Flask-Migrate (`flask db init`).
*   [ ] Add `confidence` (Float) column to `LabResult` model in `app/models/medical_report.py`.
*   [ ] Modify database structures to store multiple historical `AISummary` records (remove deletion constraint of old summaries).
*   [ ] Audit and enforce Role-Based Access Control (RBAC) validations across all route blueprints to prevent cross-account information disclosures.

---

## Phase 3: Complete Patient Daily Monitoring
*   [ ] Modernize the daily check-in UI and forms, optimizing input lengths.
*   [ ] Streamline logging flows to ensure a fast, 30-second checking interface.
*   [ ] Prevent duplicate check-in entries on a single date, updating values cleanly if logs already exist.

---

## Phase 4: Complete Medical Report Analyzer & Historical Report Comparison
*   [ ] Add confidence calculations inside `app/services/report_analyzer.py` (e.g. based on OCR character cleanliness).
*   [ ] Modify `app/routes/reports.py` and upload templates to display extraction confidence scores. Include warning banner alerts if confidence is below 85%.
*   *   Provide editable text inputs letting patients/doctors verify and adjust values before final database submission.
*   [ ] Implement a **Historical Laboratory Report Comparison** feature inside patient details, showing changes (deltas, percentages) and trend directions between old and new metrics.

---

## Phase 5: Patient Timeline & Doctor Dashboard Upgrades
*   [ ] Build a **Patient Timeline** showing clinical milestones, report uploads, medication compliance drops, symptom warnings, and notes.
*   [ ] Redesign the clinician's Patient Detail interface into a comprehensive clinical telemetry command console.
*   [ ] Update Doctor Dashboard metrics and tables, ensuring filters by condition and compliance work smoothly.

---

## Phase 6: Improve NLP & Clinical Insight Engine
*   [ ] Enhance `app/services/nlp_service.py` to extract multi-symptom trends from unstructured journal inputs.
*   [ ] Update `insight_engine.py` to raise priority alerts for consecutive low care compliance, high biometric readings, or recurring symptoms.

---

## Phase 7: Machine Learning Pipeline
*   [ ] Upgrade `app/ml/inference.py` and `app/ml/train.py` to automatically trigger model training if `.joblib` model weights are missing.
*   [ ] Document data preparation, scaling, feature engineering, and clustering methodologies.

---

## Phase 8: AI Weekly Summaries & RAG Assistant
*   [ ] Retrieve and display historical weekly summaries chronologically so doctors can observe longitudinal trends.
*   [ ] Harden Gemini RAG retrieval with fallback mechanisms when API key is missing.

---

## Phase 9: Security, Testing, & Validation
*   [ ] Run type validation, secure file upload parameters, and input sanitization audits.
*   [ ] Add new test cases to `tests/test_auth_routes.py` and `tests/test_services.py`.

---

## Phase 10: UI/UX Redesign & Final Demo Flow
*   [ ] Refactor the stylesheets (`app/static/styles.css`) to adopt a premium, modern clinical design style.
*   [ ] Complete the end-to-end clinical workflow demonstration (Doctor login -> Prescribe -> Patient daily check-in -> OCR upload -> Adherence Score update -> Insight engine alert -> Doctor timeline review).
