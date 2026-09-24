import re
import random

def calculate_confidence(line):
    """
    Simulates OCR extraction confidence based on character clean-ness.
    Noisy lines with strange punctuation decrease confidence.
    """
    # Count noise characters (excluding standard alphanumerics, spaces, and units)
    noise_chars = re.findall(r'[^a-zA-Z0-9\s.:\-/%(),\w]', line)
    base_confidence = 96.0 - len(noise_chars) * 8.0
    # Jitter to make it realistic
    base_confidence += random.uniform(-1.5, 1.5)
    return max(60.0, min(99.0, round(base_confidence, 1)))

def extract_parameters(text):
    """
    Scans text line-by-line using regular expressions to extract key laboratory
    parameters, numerical values, units, matches them to standard clinical reference ranges,
    and returns a calculated extraction confidence.
    """
    results = []
    if not text:
        return results
        
    lines = text.split('\n')
    
    # Configuration of parameters, their keywords, units, normal ranges, and value extraction regexes
    configs = [
        {
            'name': 'HbA1c',
            'keywords': [r'hba1c', r'hb\s*a1c', r'glycated\s*hemoglobin', r'a1c'],
            'unit': '%',
            'normal_range': '4.0 - 5.6',
            'regex': r'(\d{1,2}\.\d)'  # E.g., 5.7, 12.1
        },
        {
            'name': 'Fasting Glucose',
            'keywords': [r'fasting\s*glucose', r'fbs', r'glucose\s*fasting', r'fasting\s*blood\s*sugar'],
            'unit': 'mg/dL',
            'normal_range': '70 - 99',
            'regex': r'(\d{2,3})'  # E.g., 95, 140
        },
        {
            'name': 'Random Glucose',
            'keywords': [r'random\s*glucose', r'rbs', r'glucose\s*random', r'random\s*blood\s*sugar'],
            'unit': 'mg/dL',
            'normal_range': '70 - 140',
            'regex': r'(\d{2,3})'
        },
        {
            'name': 'Total Cholesterol',
            'keywords': [r'total\s*cholesterol', r'cholesterol\s*total'],
            'unit': 'mg/dL',
            'normal_range': '< 200',
            'regex': r'(\d{2,3})'
        },
        {
            'name': 'LDL Cholesterol',
            'keywords': [r'ldl\s*cholesterol', r'ldl\s*-?\s*c', r'low\s*density\s*lipoprotein'],
            'unit': 'mg/dL',
            'normal_range': '< 100',
            'regex': r'(\d{2,3})'
        },
        {
            'name': 'HDL Cholesterol',
            'keywords': [r'hdl\s*cholesterol', r'hdl\s*-?\s*c', r'high\s*density\s*lipoprotein'],
            'unit': 'mg/dL',
            'normal_range': '> 40',
            'regex': r'(\d{2,3})'
        },
        {
            'name': 'Triglycerides',
            'keywords': [r'triglycerides', r'tg\s+', r'triglyceride'],
            'unit': 'mg/dL',
            'normal_range': '< 150',
            'regex': r'(\d{2,3})'
        },
        {
            'name': 'Hemoglobin',
            'keywords': [r'hemoglobin', r'hb\s+'],
            'unit': 'g/dL',
            'normal_range': '12.0 - 17.5',
            'regex': r'(\d{1,2}\.\d)'
        },
        {
            'name': 'Vitamin D',
            'keywords': [r'vitamin\s*d', r'25\s*-\s*hydroxyvitamin\s*d', r'vit\s*d'],
            'unit': 'ng/mL',
            'normal_range': '30.0 - 100.0',
            'regex': r'(\d{1,3}(?:\.\d)?)'
        },
        {
            'name': 'Vitamin B12',
            'keywords': [r'vitamin\s*b12', r'cobalamin', r'vit\s*b12'],
            'unit': 'pg/mL',
            'normal_range': '200 - 900',
            'regex': r'(\d{3,4})'
        }
    ]
    
    # Check for BP formatted values separately since they match a fraction pattern, e.g., 120/80
    bp_keywords = [r'blood\s*pressure', r'\bbp\b']
    bp_found = False
    
    for line in lines:
        line_lower = line.lower()
        
        # Check Blood Pressure
        if not bp_found:
            for kw in bp_keywords:
                if re.search(kw, line_lower):
                    bp_match = re.search(r'(\d{2,3})\s*/\s*(\d{2,3})', line)
                    if bp_match:
                        systolic = float(bp_match.group(1))
                        diastolic = float(bp_match.group(2))
                        confidence = calculate_confidence(line)
                        
                        results.append({
                            'parameter_name': 'Systolic BP',
                            'parameter_value': systolic,
                            'unit': 'mmHg',
                            'normal_range': '90 - 120',
                            'confidence': confidence
                        })
                        results.append({
                            'parameter_name': 'Diastolic BP',
                            'parameter_value': diastolic,
                            'unit': 'mmHg',
                            'normal_range': '60 - 80',
                            'confidence': confidence
                        })
                        bp_found = True
                        break
                        
        # Check other parameters
        for cfg in configs:
            # Avoid extracting duplicate parameter records in a single document
            if any(r['parameter_name'] == cfg['name'] for r in results):
                continue
                
            for kw in cfg['keywords']:
                match_kw = re.search(kw, line_lower)
                if match_kw:
                    # Look for numerical values following the keyword in that line
                    line_after_kw = line_lower[match_kw.end():]
                    val_match = re.search(cfg['regex'], line_after_kw)
                    if val_match:
                        try:
                            val = float(val_match.group(1))
                            confidence = calculate_confidence(line)
                            results.append({
                                'parameter_name': cfg['name'],
                                'parameter_value': val,
                                'unit': cfg['unit'],
                                'normal_range': cfg['normal_range'],
                                'confidence': confidence
                            })
                            break
                        except ValueError:
                            continue
    return results
