import random
import hashlib
from datetime import datetime, timedelta, date

class BaseHealthProvider:
    """
    Abstract interface for Health/Wearable provider integrations (e.g. Fitbit, Garmin, Health Connect).
    """
    def __init__(self, credentials=None):
        self.credentials = credentials

    def connect(self) -> bool:
        raise NotImplementedError

    def disconnect(self) -> bool:
        raise NotImplementedError

    def refresh_token(self) -> bool:
        raise NotImplementedError

    def fetch_health_data(self, start_date: date, end_date: date) -> list:
        """
        Returns a list of dictionaries, where each dict represents a health metric entry:
        {
            'metric_type': 'steps',
            'value': 8420,
            'unit': 'steps',
            'timestamp': datetime(...),
            'source': 'wearable',
            'confidence': 1.0,
            'external_record_id': '...'
        }
        """
        raise NotImplementedError


class MockHealthProvider(BaseHealthProvider):
    """
    Mock health provider generating realistic, disease-specific telemetry data.
    All data is clearly tagged as demo data.
    """
    def connect(self) -> bool:
        return True

    def disconnect(self) -> bool:
        return True

    def refresh_token(self) -> bool:
        return True

    def fetch_health_data(self, start_date: date, end_date: date, patient_id=None, primary_condition=None, base_weight=80.0) -> list:
        metrics = []
        current_date = start_date
        
        while current_date <= end_date:
            # Seed the random number generator using patient_id and date for reproducibility
            seed_str = f"{patient_id}-{current_date}"
            seed_hash = int(hashlib.md5(seed_str.encode()).hexdigest(), 16)
            random.seed(seed_hash)
            
            # Formulate timestamp (e.g., noon or throughout the day)
            dt_noon = datetime.combine(current_date, datetime.min.time()) + timedelta(hours=12)
            
            # Adapt profiles based on primary condition
            # Progress over time: we drift metrics positively or negatively depending on compliance
            day_idx = (current_date - start_date).days
            
            # General trends (improving steps/sleep/weight)
            steps_trend = 1.0 + (day_idx * 0.005)  # slow increase in steps
            sleep_trend = 1.0 + (day_idx * 0.002)  # slow increase in sleep
            weight_trend = 1.0 - (day_idx * 0.0006) # slow decrease in weight
            
            # --- STEPS & CALORIES & ACTIVE MINUTES ---
            base_steps = 5000
            if primary_condition == "Obesity":
                base_steps = 4200
            elif primary_condition == "Heart Disease":
                base_steps = 4500
                
            steps_val = int(base_steps * steps_trend + random.randint(-800, 800))
            steps_val = max(0, steps_val)
            
            metrics.append({
                'metric_type': 'steps',
                'value': float(steps_val),
                'unit': 'steps',
                'timestamp': dt_noon,
                'source': 'health_platform',
                'confidence': 1.0,
                'external_record_id': f"mock_steps_{current_date.strftime('%Y%m%d')}"
            })
            
            # Calories: ~ 0.04 * steps + 1600 (BMR)
            calories_val = round((steps_val * 0.045) + 1600 + random.randint(-150, 150), 1)
            metrics.append({
                'metric_type': 'calories',
                'value': calories_val,
                'unit': 'kcal',
                'timestamp': dt_noon,
                'source': 'health_platform',
                'confidence': 1.0,
                'external_record_id': f"mock_cal_{current_date.strftime('%Y%m%d')}"
            })
            
            # Active Minutes: steps / 150
            active_min = int(steps_val / 150 + random.randint(-5, 5))
            active_min = max(0, active_min)
            metrics.append({
                'metric_type': 'active_minutes',
                'value': float(active_min),
                'unit': 'minutes',
                'timestamp': dt_noon,
                'source': 'health_platform',
                'confidence': 1.0,
                'external_record_id': f"mock_act_{current_date.strftime('%Y%m%d')}"
            })
            
            # --- SLEEP ---
            base_sleep = 6.2
            sleep_val = round(base_sleep * sleep_trend + random.uniform(-0.8, 1.2), 1)
            sleep_val = max(0.0, min(24.0, sleep_val))
            metrics.append({
                'metric_type': 'sleep',
                'value': sleep_val,
                'unit': 'hours',
                'timestamp': dt_noon - timedelta(hours=6), # recorded in morning
                'source': 'wearable',
                'confidence': 1.0,
                'external_record_id': f"mock_sleep_{current_date.strftime('%Y%m%d')}"
            })
            
            # --- HEART RATE & RESTING HEART RATE ---
            base_rhr = 72
            if primary_condition == "Heart Disease" or primary_condition == "Hypertension":
                base_rhr = 78
            
            rhr_val = int(base_rhr - (day_idx * 0.04) + random.randint(-3, 3))
            metrics.append({
                'metric_type': 'resting_heart_rate',
                'value': float(rhr_val),
                'unit': 'bpm',
                'timestamp': dt_noon - timedelta(hours=4), # morning resting HR
                'source': 'wearable',
                'confidence': 1.0,
                'external_record_id': f"mock_rhr_{current_date.strftime('%Y%m%d')}"
            })
            
            avg_hr_val = int(rhr_val + 10 + (steps_val / 800) + random.randint(-4, 4))
            metrics.append({
                'metric_type': 'heart_rate',
                'value': float(avg_hr_val),
                'unit': 'bpm',
                'timestamp': dt_noon,
                'source': 'wearable',
                'confidence': 1.0,
                'external_record_id': f"mock_hr_{current_date.strftime('%Y%m%d')}"
            })
            
            # --- WEIGHT ---
            weight_val = round(base_weight * weight_trend + random.uniform(-0.3, 0.3), 1)
            metrics.append({
                'metric_type': 'weight',
                'value': weight_val,
                'unit': 'kg',
                'timestamp': dt_noon - timedelta(hours=4),
                'source': 'health_platform',  # e.g., smart scale
                'confidence': 1.0,
                'external_record_id': f"mock_wt_{current_date.strftime('%Y%m%d')}"
            })
            
            # --- BLOOD PRESSURE (Hypertension specific) ---
            base_sbp = 120
            base_dbp = 80
            if primary_condition == "Hypertension":
                base_sbp = 142 - (day_idx * 0.15) # gradual improvement
                base_dbp = 88 - (day_idx * 0.08)
                
            sbp_val = int(base_sbp + random.randint(-6, 6))
            dbp_val = int(base_dbp + random.randint(-4, 4))
            
            metrics.append({
                'metric_type': 'blood_pressure_systolic',
                'value': float(sbp_val),
                'unit': 'mmHg',
                'timestamp': dt_noon - timedelta(hours=3),
                'source': 'medical_device',
                'confidence': 1.0,
                'external_record_id': f"mock_bps_{current_date.strftime('%Y%m%d')}"
            })
            metrics.append({
                'metric_type': 'blood_pressure_diastolic',
                'value': float(dbp_val),
                'unit': 'mmHg',
                'timestamp': dt_noon - timedelta(hours=3),
                'source': 'medical_device',
                'confidence': 1.0,
                'external_record_id': f"mock_bpd_{current_date.strftime('%Y%m%d')}"
            })
            
            # --- BLOOD GLUCOSE (Diabetes specific) ---
            if primary_condition == "Type 2 Diabetes":
                base_bg = 155 - (day_idx * 0.3)
                bg_val = round(base_bg + random.randint(-20, 20), 1)
                metrics.append({
                    'metric_type': 'blood_glucose',
                    'value': bg_val,
                    'unit': 'mg/dL',
                    'timestamp': dt_noon - timedelta(hours=4), # fasting reading
                    'source': 'medical_device',
                    'confidence': 1.0,
                    'external_record_id': f"mock_bg_{current_date.strftime('%Y%m%d')}"
                })
                
            # --- SpO2 ---
            spo2_val = round(98.0 - random.uniform(0, 1.5), 1)
            metrics.append({
                'metric_type': 'spo2',
                'value': spo2_val,
                'unit': '%',
                'timestamp': dt_noon,
                'source': 'wearable',
                'confidence': 1.0,
                'external_record_id': f"mock_spo2_{current_date.strftime('%Y%m%d')}"
            })
            
            # Increment current date
            current_date += timedelta(days=1)
            
        return metrics
