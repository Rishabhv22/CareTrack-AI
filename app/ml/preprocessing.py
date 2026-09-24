import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler

def generate_synthetic_ml_data(num_samples=1000, seed=42):
    """
    Generates realistic synthetic data for chronic patient progress tracking.
    Features:
      - med_adherence: 0.0 to 1.0 (medication compliance rate)
      - exercise_consistency: 0.0 to 1.0 (exercise consistency)
      - diet_compliance: 0.0 to 1.0 (diet compliance rate)
      - weight_change: weight difference over 30 days (-5.0 to +3.0 kg)
      - glucose_change: blood glucose change over 30 days (-80 to +80 mg/dL)
      - sleep_avg: average sleep hours (4.0 to 10.0 hours)
    
    Target:
      - progress_label: 0 = Deteriorating, 1 = Stable, 2 = Improving
    """
    np.random.seed(seed)
    
    med_adherence = np.random.uniform(0.1, 1.0, num_samples)
    exercise_consistency = np.random.uniform(0.0, 1.0, num_samples)
    diet_compliance = np.random.uniform(0.1, 1.0, num_samples)
    sleep_avg = np.random.normal(7.0, 1.0, num_samples)
    sleep_avg = np.clip(sleep_avg, 4.0, 10.0)
    
    # Weight change and glucose change correlate with compliance
    weight_change = -3.0 * med_adherence - 2.0 * exercise_consistency + np.random.normal(1.5, 0.8, num_samples)
    glucose_change = -50.0 * med_adherence - 30.0 * diet_compliance + np.random.normal(30, 15, num_samples)
    
    # Assign target labels based on rules + noise
    # Improving: high compliance, negative change in glucose/weight
    # Deteriorating: low compliance, positive weight/glucose changes
    progress_score = (
        2.5 * med_adherence + 
        1.5 * exercise_consistency + 
        1.5 * diet_compliance - 
        0.5 * weight_change - 
        0.02 * glucose_change + 
        np.random.normal(0, 0.5, num_samples)
    )
    
    labels = []
    for score in progress_score:
        if score > 3.8:
            labels.append(2)  # Improving
        elif score < 2.2:
            labels.append(0)  # Deteriorating
        else:
            labels.append(1)  # Stable
            
    df = pd.DataFrame({
        'med_adherence': med_adherence,
        'exercise_consistency': exercise_consistency,
        'diet_compliance': diet_compliance,
        'weight_change': weight_change,
        'glucose_change': glucose_change,
        'sleep_avg': sleep_avg,
        'progress_label': labels
    })
    
    return df

def prepare_data(df):
    """
    Splits features and targets, performs train/test splits, and scales features.
    """
    X = df.drop(columns=['progress_label'])
    y = df['progress_label']
    
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42, stratify=y)
    
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)
    
    return X_train_scaled, X_test_scaled, y_train, y_test, scaler
