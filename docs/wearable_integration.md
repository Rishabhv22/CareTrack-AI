# Wearable & Health Data Integration Architecture

This document describes the design, data pipelines, database models, and future implementation guidelines for integrating smart wearables (Fitbit, Garmin, Apple HealthKit, Android Health Connect) into the **CareTrack AI** platform.

---

## 1. Core Architecture Overview

CareTrack AI provides a multi-source, asynchronous health data layer designed for maximum flexibility, traceability, and clinical safety. The flow is structured as:

```
[Smart Wearable / Platform]
            ↓ (OAuth2 / Web API / SDK)
  [Provider Adapter] (e.g. MockHealthProvider)
            ↓ (Normalization & Source Tagging)
    [HealthMetric Model]
            ↓ (Data Validation & Quality Checks)
[DailyHealthSummary Aggregation] → (Updates Patient weight/BMI baselines)
            ↓
  [Clinical Insight Engine] → (Generates Patient Trends & Clinician Flags)
            ↓
   [Doctor Detail Panel] / [AI Weekly Summary Context]
```

Every incoming value is explicitly tagged with a `source` (`manual`, `wearable`, `health_platform`, `medical_device`, `medical_report`) to guarantee auditing separation.

---

## 2. Database Design

Three primary tables manage continuous monitoring telemetry:

### A. `WearableDevice`
Stores device connection states and encrypted OAuth credentials (never exposed to the frontend):
- `id` (UUID string)
- `patient_id` (foreign key)
- `provider` (e.g. 'Fitbit', 'Demo Wearable')
- `device_name` / `device_type` (e.g. 'Smartwatch')
- `connection_status` ('CONNECTED', 'DISCONNECTED')
- `access_token` / `refresh_token` / `token_expiry`
- `last_synced_at`

### B. `HealthMetric`
Stores raw physiological readings and time-series telemetry logs:
- `id` (UUID string)
- `patient_id` (foreign key)
- `metric_type` (e.g. 'steps', 'sleep', 'heart_rate', 'resting_heart_rate', 'weight', 'blood_pressure_systolic', 'blood_pressure_diastolic', 'blood_glucose', 'spo2')
- `value` (float)
- `unit` (string)
- `timestamp` (datetime)
- `source` (string)
- `confidence` (float: 1.0 = normal, 0.9/0.8 = flagged questionable reading)
- Unique constraint: `(patient_id, metric_type, timestamp)` to block duplicate entries during incremental syncs.

### C. `DailyHealthSummary`
Aggregates hourly/daily telemetry into a single day-level row for dashboard performance:
- `patient_id`, `date` (Unique primary key combination)
- `total_steps`, `calories_burned`, `active_minutes`
- `average_heart_rate`, `resting_heart_rate`, `sleep_hours`, `weight`
- `systolic_bp`, `diastolic_bp`, `blood_glucose`, `spo2`
- `data_sources` (JSON string tracking source ownership per metric)

---

## 3. Data Validation & Clinical Safety Bounds

The system enforces safety boundaries on all physiological data imports:

| Metric Type | Technical Bounds | Questionable Drift Alert Bounds | Action taken if Questionable |
| :--- | :--- | :--- | :--- |
| **Steps** | `>= 0` | `> 50,000 steps/day` | Lowers confidence (0.5), ignores as technical glitch. |
| **Heart Rate** | `30 - 220 BPM` | `< 40 BPM` (Bradycardia) or `> 100 BPM` (Tachycardia) resting | Confidence = 0.9, generates active clinician alert. |
| **Blood Pressure**| `BP > 30` | `SBP > 180` or `DBP > 110` mmHg | Confidence = 0.9, generates **HIGH** severity alert. |
| **Glucose** | `10 - 1000` | `< 55 mg/dL` (Hypo) or `> 280 mg/dL` (Hyper) | Confidence = 0.9, generates **HIGH** severity alert. |
| **SpO2** | `0 - 100%` | `< 90%` (Hypoxia) | Confidence = 0.8, generates **HIGH** severity alert. |

---

## 4. Future Integration Roadmap

To transition from the `MockHealthProvider` to real-world production platforms, implement the following connectors:

### A. Fitbit Web API (OAuth2)
1. **Redirect User:** Direct patient to Fitbit authorization URL.
2. **Handle Callback:** Redirect back to `/api/patient/wearables/callback`, exchange authorization code for access and refresh tokens, and store them securely in `WearableDevice`.
3. **Data Sync Job:** Fetch `/1/user/-/activities/steps/date/today/1m.json` for fine-grained steps, or corresponding physiological logs.

### B. Google Health Connect (Android SDK)
1. **App Permissions:** Prompt patient inside the Android application to share steps, heart rate, sleep, blood glucose, etc.
2. **Local Sync:** Retrieve telemetry locally via Java/Kotlin Health Connect Client SDK.
3. **JSON Sync POST:** Post data arrays incrementally to `/api/patient/health-metrics` using JWT/session authentication.

### C. Apple HealthKit (iOS)
1. **Authorization:** Request read access for `HKQuantityTypeIdentifierStepCount`, `HKCategoryTypeIdentifierSleepAnalysis`, etc.
2. **Background Delivery:** Setup Apple HealthKit background sync observers to fire updates.
3. **POST sync requests:** Send updates to the CareTrack API endpoints.

---

## 5. Security & Privacy Considerations

1. **Role Isolation:** Patient endpoints block clinician inputs; doctor endpoints enforce `patient in doctor.patients` checks to prevent HIPAA leaks.
2. **Access Revocation:** Toggling `health_data_consent = False` immediately stops future syncs, sets connection status to `DISCONNECTED`, and logs the action in the security audit trails.
