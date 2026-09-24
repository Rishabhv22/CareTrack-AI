import pytest
from app.services.bmi_service import calculate_bmi, get_bmi_category, get_bmi_interpretation
from app.services.nlp_service import analyze_journal
from app.services.report_analyzer import extract_parameters

def test_bmi_calculation():
    # Normal BMI calculation
    assert calculate_bmi(70, 175) == 22.9
    # Underweight case
    assert calculate_bmi(50, 180) == 15.4
    # Obese case
    assert calculate_bmi(100, 170) == 34.6
    # Edge case: zero height
    assert calculate_bmi(70, 0) == 0.0
    
def test_bmi_categories():
    assert get_bmi_category(16.0) == "Underweight"
    assert get_bmi_category(22.0) == "Normal weight"
    assert get_bmi_category(28.0) == "Overweight"
    assert get_bmi_category(35.0) == "Obese"
    
def test_nlp_journal_symptoms_extraction():
    # Normal symptom extraction
    nlp_result = analyze_journal("I felt very tired today and had a light headache. Took my diabetes medication.")
    assert "fatigue" in nlp_result["symptoms"]
    assert "headache" in nlp_result["symptoms"]
    assert nlp_result["medications"] == "Medication Taken"
    assert nlp_result["concerning_flag"] is False
    
def test_nlp_journal_negation():
    # Negation check test
    # "no pain" should not return "pain" as active symptom
    nlp_result = analyze_journal("I feel good. I have no pain today.")
    assert "pain" not in nlp_result["symptoms"]
    
def test_nlp_journal_concerning_symptoms():
    # Severe chest pain trigger
    nlp_result = analyze_journal("I experienced severe chest pain while walking.")
    assert nlp_result["concerning_flag"] is True
    
def test_report_parameter_extraction():
    # Test regex parsing on raw OCR text lines
    sample_text = (
        "Patient Report\n"
        "Fasting Blood Sugar: 126 mg/dL\n"
        "HbA1c (Glycated Hemoglobin): 7.2 %\n"
        "BP: 135/85 mmHg\n"
        "Total Cholesterol: 240 mg/dL"
    )
    
    extracted = extract_parameters(sample_text)
    
    # Check HbA1c
    hba1c_res = next((x for x in extracted if x['parameter_name'] == 'HbA1c'), None)
    assert hba1c_res is not None
    assert hba1c_res['parameter_value'] == 7.2
    assert hba1c_res['unit'] == '%'
    assert 'confidence' in hba1c_res
    assert 60.0 <= hba1c_res['confidence'] <= 99.0
    
    # Check Fasting Glucose
    glucose_res = next((x for x in extracted if x['parameter_name'] == 'Fasting Glucose'), None)
    assert glucose_res is not None
    assert glucose_res['parameter_value'] == 126.0
    assert 'confidence' in glucose_res
    assert 60.0 <= glucose_res['confidence'] <= 99.0
    
    # Check BP
    sbp_res = next((x for x in extracted if x['parameter_name'] == 'Systolic BP'), None)
    assert sbp_res is not None
    assert sbp_res['parameter_value'] == 135.0
    assert 'confidence' in sbp_res
    assert 60.0 <= sbp_res['confidence'] <= 99.0
    
    dbp_res = next((x for x in extracted if x['parameter_name'] == 'Diastolic BP'), None)
    assert dbp_res is not None
    assert dbp_res['parameter_value'] == 85.0
    assert 'confidence' in dbp_res
    assert 60.0 <= dbp_res['confidence'] <= 99.0
