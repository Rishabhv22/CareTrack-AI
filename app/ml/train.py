import os
import joblib
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.cluster import KMeans
from sklearn.metrics import classification_report, accuracy_score, silhouette_score
from app.ml.preprocessing import generate_synthetic_ml_data, prepare_data

def train_models():
    """
    Trains the Random Forest, Logistic Regression, and K-Means models
    on synthetic chronic care logs. Saves models and scalers.
    """
    print("Generating synthetic care logs dataset...")
    df = generate_synthetic_ml_data(num_samples=1200)
    
    print("Preprocessing data and splitting features...")
    X_train, X_test, y_train, y_test, scaler = prepare_data(df)
    
    # 1. Train Random Forest Classifier
    print("Training Random Forest Classifier...")
    rf_model = RandomForestClassifier(n_estimators=100, max_depth=8, random_state=42)
    rf_model.fit(X_train, y_train)
    
    rf_preds = rf_model.predict(X_test)
    rf_acc = accuracy_score(y_test, rf_preds)
    print(f"Random Forest Accuracy: {rf_acc * 100:.2f}%")
    print(classification_report(y_test, rf_preds, target_names=['Deteriorating', 'Stable', 'Improving']))
    
    # 2. Train Logistic Regression Classifier (For Comparison)
    print("Training Logistic Regression Classifier...")
    lr_model = LogisticRegression(max_iter=500, random_state=42)
    lr_model.fit(X_train, y_train)
    lr_preds = lr_model.predict(X_test)
    lr_acc = accuracy_score(y_test, lr_preds)
    print(f"Logistic Regression Accuracy: {lr_acc * 100:.2f}%")
    
    # 3. Train K-Means Clustering on Compliance features
    print("Training K-Means Clustering for Care Archetypes...")
    # Selectmedication, exercise, and diet compliance features
    compliance_features = df[['med_adherence', 'exercise_consistency', 'diet_compliance']]
    kmeans = KMeans(n_clusters=3, random_state=42, n_init=10)
    kmeans.fit(compliance_features)
    
    sil_score = silhouette_score(compliance_features, kmeans.labels_)
    print(f"K-Means Clustering Silhouette Score: {sil_score:.3f}")
    
    # Ensure save directory exists
    save_dir = os.path.join(os.path.dirname(__file__), 'models')
    os.makedirs(save_dir, exist_ok=True)
    
    # Save the models and preprocessor scaler
    print("Saving models to disk...")
    joblib.dump(rf_model, os.path.join(save_dir, 'rf_classifier.joblib'))
    joblib.dump(scaler, os.path.join(save_dir, 'scaler.joblib'))
    joblib.dump(kmeans, os.path.join(save_dir, 'kmeans_cluster.joblib'))
    
    print("Training complete! Models saved in app/ml/models/")

if __name__ == '__main__':
    train_models()
