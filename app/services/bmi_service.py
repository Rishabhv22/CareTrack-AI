def calculate_bmi(weight_kg, height_cm):
    """
    Calculates BMI given weight in kilograms and height in centimeters.
    Formula: BMI = weight (kg) / [height (m)]^2
    """
    if not weight_kg or not height_cm or height_cm <= 0:
        return 0.0
    height_m = height_cm / 100.0
    bmi = weight_kg / (height_m ** 2)
    return round(bmi, 1)

def get_bmi_category(bmi):
    """
    Returns standard BMI category.
    """
    if bmi < 18.5:
        return "Underweight"
    elif 18.5 <= bmi < 25.0:
        return "Normal weight"
    elif 25.0 <= bmi < 30.0:
        return "Overweight"
    else:
        return "Obese"

def get_bmi_interpretation(bmi):
    """
    Returns an educational interpretation.
    Disclaimer: BMI is a general screening indicator and not a diagnostic index.
    """
    category = get_bmi_category(bmi)
    interpretation = {
        "Underweight": "Below typical weight range. Discuss your nutrition with a healthcare provider.",
        "Normal weight": "Typical weight range. Maintain a balanced diet and regular physical activity.",
        "Overweight": "Slightly above typical weight range. Focus on healthy nutrition and exercise.",
        "Obese": "Significantly above typical weight range. Consider consulting your clinician for tailored guidelines."
    }
    return interpretation.get(category, "N/A")
