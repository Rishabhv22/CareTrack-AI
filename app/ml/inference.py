import os
import joblib
import json
import numpy as np
from datetime import datetime, timedelta
from app.extensions import db
from app.models.daily_log import DailyHealthLog
from app.models.medication import Medication, MedicationLog
from app.models.prediction import Prediction
from app.services.compliance_engine import calculate_adherence_score

def get_models_path():
    base_dir = os.path.dirname(__file__)
    return {
        'rf': os.path.join(base_dir, 'models', 'rf_classifier.joblib'),
        'scaler': os.path.join(base_dir, 'models', 'scaler.joblib'),
        'kmeans': os.path.join(base_dir, 'models', 'kmeans_cluster.joblib')
    }

def ensure_models_trained():
    paths = get_models_path()
    if not (os.path.exists(paths['rf']) and os.path.exists(paths['scaler']) and os.path.exists(paths['kmeans'])):
        print("ML models missing. Training models now...")
        from app.ml.train import train_models
        train_models()

def predict_patient_progress(patient):
    """
    Gathers 30-day health stats for a patient, scales features,
    loads the trained Random Forest model, and predicts progress label.
    Saves prediction metadata to the database.
    """
    ensure_models_trained()
    paths = get_models_path()
    
    today = datetime.utcnow().date()
    start_date = today - timedelta(days=30)
    
    # 1. Fetch patient logs
    logs = DailyHealthLog.query.filter(
        DailyHealthLog.patient_id == patient.id,
        DailyHealthLog.log_date >= start_date
    ).order_by(DailyHealthLog.log_date.asc()).all()
    
    log_count = len(logs)
    
    # Check if baseline data exists (at least 3 logs required)
    if log_count < 3:
        return {
            'prediction': 'Stable (Inconclusive)',
            'confidence': 1.0,
            'features': {}
        }
        
    # 2. Extract Features
    # Med adherence
    score_data = calculate_adherence_score(patient, days=30)
    med_adherence = score_data['medication']['ratio']
    
    # Exercise & Diet ratios
    exercise_consistency = score_data['exercise']['ratio']
    diet_compliance = score_data['diet']['ratio']
    
    # Sleep average
    sleeps = [l.sleep_hours for l in logs if l.sleep_hours is not None]
    sleep_avg = sum(sleeps) / len(sleeps) if sleeps else 7.0
    
    # Weight change
    weights = [l.weight for l in logs if l.weight is not None]
    weight_change = weights[-1] - weights[0] if len(weights) >= 2 else 0.0
    
    # Glucose change
    glucoses = [l.blood_glucose for l in logs if l.blood_glucose is not None]
    glucose_change = glucoses[-1] - glucoses[0] if len(glucoses) >= 2 else 0.0
    
    features = {
        'med_adherence': float(med_adherence),
        'exercise_consistency': float(exercise_consistency),
        'diet_compliance': float(diet_compliance),
        'weight_change': float(weight_change),
        'glucose_change': float(glucose_change),
        'sleep_avg': float(sleep_avg)
    }
    
    # 3. Load model and run inference
    try:
        rf_model = joblib.load(paths['rf'])
        scaler = joblib.load(paths['scaler'])
        
        # Prepare inputs as a list of lists matching training feature order:
        # ['med_adherence', 'exercise_consistency', 'diet_compliance', 'weight_change', 'glucose_change', 'sleep_avg']
        features_list = [[
            features['med_adherence'],
            features['exercise_consistency'],
            features['diet_compliance'],
            features['weight_change'],
            features['glucose_change'],
            features['sleep_avg']
        ]]
        
        scaled_features = scaler.transform(features_list)
        
        # Predict class & probabilities
        pred_class = int(rf_model.predict(scaled_features)[0])
        probabilities = rf_model.predict_proba(scaled_features)[0]
        confidence = float(probabilities[pred_class])
        
        class_mapping = {0: 'Deteriorating', 1: 'Stable', 2: 'Improving'}
        pred_label = class_mapping.get(pred_class, 'Stable')
        
        # Save prediction record in DB
        Prediction.query.filter_by(patient_id=patient.id).delete() # Keep latest
        pred_log = Prediction(
            patient_id=patient.id,
            model_name='Random Forest Classifier',
            prediction_result=pred_label,
            features_used=json.dumps(features),
            confidence_score=confidence
        )
        db.session.add(pred_log)
        db.session.commit()
        
        return {
            'prediction': pred_label,
            'confidence': confidence,
            'features': features
        }
    except Exception as e:
        print(f"Error during ML inference: {str(e)}")
        return {
            'prediction': 'Stable (Inconclusive)',
            'confidence': 1.0,
            'features': features
        }

def get_compliance_archetype(patient):
    """
    K-Means clustering inference. Groups patients into archetypes.
    """
    ensure_models_trained()
    paths = get_models_path()
    
    score_data = calculate_adherence_score(patient, days=30)
    features = [
        score_data['medication']['ratio'],
        score_data['exercise']['ratio'],
        score_data['diet']['ratio']
    ]
    
    try:
        kmeans = joblib.load(paths['kmeans'])
        cluster = int(kmeans.predict([features])[0])
        
        # Cluster labels interpretation
        # K-Means group descriptions:
        cluster_mapping = {
            0: "Highly Compliant Adherent",
            1: "Struggling with Lifestyle Routines",
            2: "Sub-Optimal Adherence & Missing Check-ins"
        }
        return cluster_mapping.get(cluster, "Standard Care Tracker")
    except Exception:
        return "Standard Care Tracker"
