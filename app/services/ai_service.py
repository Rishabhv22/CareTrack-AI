import os
import re
from datetime import datetime, timedelta
# TODO: Move to the new google.genai SDK (google-genai) once API compatibility is verified
import google.generativeai as genai
from flask import current_app
from app.extensions import db
from app.models.daily_log import DailyHealthLog
from app.models.medication import Medication, MedicationLog
from app.models.recommendation import AISummary, Alert
from app.services.compliance_engine import calculate_adherence_score

def generate_patient_summary(patient, days=30):
    """
    Generates a 30-day clinical progress summary for a patient.
    Uses the Google Gemini API if a key is provided, otherwise falls back
    to a rule-based statistical summary generator.
    """
    today = datetime.utcnow().date()
    start_date = today - timedelta(days=days)
    
    # 1. Compile patient metrics context
    score_data = calculate_adherence_score(patient, days)
    
    logs = DailyHealthLog.query.filter(
        DailyHealthLog.patient_id == patient.id,
        DailyHealthLog.log_date >= start_date
    ).all()
    
    # Calculate averages from manual logs
    manual_weights = [l.weight for l in logs if l.weight is not None]
    glucoses = [l.blood_glucose for l in logs if l.blood_glucose is not None]
    bp_systolics = [l.systolic_bp for l in logs if l.systolic_bp is not None]
    
    avg_glucose = round(sum(glucoses) / len(glucoses), 1) if glucoses else "N/A"
    manual_weight_change = round(manual_weights[-1] - manual_weights[0], 1) if len(manual_weights) >= 2 else "N/A"
    avg_bp = f"{round(sum(bp_systolics)/len(bp_systolics))}/{round(sum([l.diastolic_bp for l in logs if l.diastolic_bp is not None])/sum(1 for l in logs if l.diastolic_bp is not None))}" if bp_systolics else "N/A"
    
    # Fetch wearable summaries
    from app.models.wearable import DailyHealthSummary
    summaries = DailyHealthSummary.query.filter(
        DailyHealthSummary.patient_id == patient.id,
        DailyHealthSummary.date >= start_date
    ).all()
    
    wearable_steps = [s.total_steps for s in summaries if s.total_steps is not None]
    wearable_sleep = [s.sleep_hours for s in summaries if s.sleep_hours is not None]
    wearable_rhr = [s.resting_heart_rate for s in summaries if s.resting_heart_rate is not None]
    wearable_spo2 = [s.spo2 for s in summaries if s.spo2 is not None]
    wearable_weights = [s.weight for s in summaries if s.weight is not None]
    
    avg_steps = int(sum(wearable_steps) / len(wearable_steps)) if wearable_steps else "N/A"
    avg_sleep = round(sum(wearable_sleep) / len(wearable_sleep), 1) if wearable_sleep else "N/A"
    avg_resting_hr = int(sum(wearable_rhr) / len(wearable_rhr)) if wearable_rhr else "N/A"
    avg_spo2 = round(sum(wearable_spo2) / len(wearable_spo2), 1) if wearable_spo2 else "N/A"
    wearable_weight_change = round(wearable_weights[-1] - wearable_weights[0], 1) if len(wearable_weights) >= 2 else "N/A"
    
    # Gather symptoms list
    symptom_logs = [l.symptoms for l in logs if l.symptoms]
    
    # Gather missed med counts
    missed_meds_count = 0
    meds = Medication.query.filter_by(patient_id=patient.id, is_active=True).all()
    for med in meds:
        missed_meds_count += MedicationLog.query.filter(
            MedicationLog.medication_id == med.id,
            MedicationLog.log_date >= start_date,
            MedicationLog.status == 'MISSED'
        ).count()
        
    # Construct context text
    context = (
        f"Patient Name: {patient.name}\n"
        f"Age: {patient.age} | Gender: {patient.gender}\n"
        f"Primary Condition: {patient.primary_condition}\n"
        f"Monitoring Period: Last {days} Days\n"
        f"Care Adherence Score: {score_data['total']}/100\n"
        f"  - Medication score: {score_data['medication']['score']}/40\n"
        f"  - Daily logging score: {score_data['logging']['score']}/10 (Logged {score_data['logging']['count']} days)\n"
        f"  - Exercise consistency score: {score_data['exercise']['score']}/20\n"
        f"  - Diet compliance score: {score_data['diet']['score']}/20\n"
        f"Wearable Device Metrics:\n"
        f"  - Average Steps: {avg_steps} steps/day\n"
        f"  - Average Sleep: {avg_sleep} hours/night\n"
        f"  - Average Resting Heart Rate: {avg_resting_hr} BPM\n"
        f"  - Average SpO2: {avg_spo2}%\n"
        f"  - Weight drift (from scale): {wearable_weight_change} kg\n"
        f"Biometric Trends (Manual/Clinic):\n"
        f"  - Weight change: {manual_weight_change} kg\n"
        f"  - Average Fasting Glucose: {avg_glucose} mg/dL\n"
        f"  - Average Blood Pressure: {avg_bp} mmHg\n"
        f"Compliance Issues:\n"
        f"  - Missed doses counted: {missed_meds_count} times\n"
        f"Patient Symptom Logs: {', '.join(symptom_logs) if symptom_logs else 'None reported'}\n"
    )

    summary_text = ""
    api_key = current_app.config.get('GEMINI_API_KEY')
    
    # 2. Call Gemini API if key is set
    if api_key:
        try:
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel('gemini-1.5-flash')
            
            prompt = (
                "You are CareTrack AI, an expert clinical support assistant. "
                "Analyze the following patient logging data and write a concise, professional, "
                "structured progress summary for the attending doctor. "
                "Follow these strict directives:\n"
                "1. Focus solely on objective observations, compliance rates, wearable device telemetry trends, and highlights.\n"
                "2. List specific 'Items for Clinician Review' (e.g. repeated missed doses, concerning symptom logs, BP spikes, or missing wearable data).\n"
                "3. NEVER diagnose the patient or state that they have a new condition.\n"
                "4. NEVER instruct the doctor to stop, change, or prescribe specific drugs or dosages.\n"
                "5. Conclude with: 'This summary is an AI-assisted analysis of patient logs and device metrics. The attending clinician remains the final decision-maker.'\n\n"
                f"Patient Logging Context:\n{context}"
            )
            
            response = model.generate_content(prompt)
            summary_text = response.text.strip()
            
        except Exception as e:
            current_app.logger.error(f"Gemini API summary generation failed: {str(e)}. Using fallback summarizer.")
            summary_text = ""
            
    # 3. Fallback Rule-Based Summary Builder
    if not summary_text:
        # Create a beautiful structured Markdown fallback
        summary_lines = [
            f"### Patient Progress Summary (30-Day Logs)",
            f"**Patient:** {patient.name} | **Monitored Condition:** {patient.primary_condition}",
            f"",
            f"**Adherence Overview:**",
            f"- **Care Adherence Score:** {score_data['total']} / 100",
            f"- **Medication Compliance:** {round(score_data['medication']['ratio'] * 100)}% adherence rate.",
            f"- **Logging Frequency:** Logged {score_data['logging']['count']} out of {days} days ({round(score_data['logging']['ratio'] * 100)}%).",
            f"- **Exercise Consistency:** Logged exercise or reached activity targets on {score_data['exercise']['count']} days.",
            f"",
            f"**Wearable Device Observations (Demo Wearable):**",
            f"- **Average Steps:** {avg_steps} steps/day." if avg_steps != "N/A" else "- **Average Steps:** No step telemetry recorded.",
            f"- **Average Sleep:** {avg_sleep} hours/night." if avg_sleep != "N/A" else "- **Average Sleep:** No sleep telemetry recorded.",
            f"- **Average Resting HR:** {avg_resting_hr} BPM." if avg_resting_hr != "N/A" else "- **Average Resting HR:** No resting heart rate telemetry.",
            f"- **Weight Shift (Scale):** {wearable_weight_change} kg over this period." if wearable_weight_change != "N/A" else "- **Weight Shift (Scale):** Baseline weight tracking inactive.",
            f"",
            f"**Manual Biometric Observations:**",
            f"- **Weight Trend:** Manual weight shifted by {manual_weight_change} kg." if manual_weight_change != "N/A" else "- **Weight Trend:** Manual weight logging incomplete.",
            f"- **Average Blood Glucose:** {avg_glucose} mg/dL." if avg_glucose != "N/A" else "- **Average Blood Glucose:** No blood glucose measurements recorded.",
            f"- **Average Blood Pressure:** {avg_bp} mmHg." if avg_bp != "N/A" else "- **Average Blood Pressure:** No BP measurements recorded.",
            f"",
            f"**Items for Clinician Review:**"
        ]
        
        issues = []
        if missed_meds_count > 0:
            issues.append(f"Missed prescribed medications logged {missed_meds_count} times in the last 30 days.")
        if score_data['total'] < 60:
            issues.append(f"Low overall care adherence score flagged ({score_data['total']}%).")
        if symptom_logs:
            issues.append(f"Physical symptoms reported: {'; '.join(symptom_logs[:3])}.")
        if glucoses and any(g > 200 for g in glucoses):
            issues.append("Patient logged blood glucose values exceeding 200 mg/dL.")
        if bp_systolics and any(sys > 140 for sys in bp_systolics):
            issues.append("Patient logged systolic blood pressure values exceeding 140 mmHg.")
        if not summaries:
            issues.append("No active smart wearable device connected or synchronization is lagging.")
            
        if not issues:
            summary_lines.append("- No critical compliance issues or biometric deviations detected.")
        else:
            for issue in issues:
                summary_lines.append(f"- **[Flag]** {issue}")
                
        summary_lines.append("")
        summary_lines.append("> [!NOTE]")
        summary_lines.append("> This summary is an AI-assisted analysis of patient logs and device metrics. The attending clinician remains the final decision-maker.")
        
        summary_text = "\n".join(summary_lines)

    # 4. Save summary to database
    # Preserve previous summaries in database for historical timelines
    
    ai_summary = AISummary(
        patient_id=patient.id,
        summary_text=summary_text,
        start_date=start_date,
        end_date=today
    )
    db.session.add(ai_summary)
    db.session.commit()
    
    return summary_text

# Medical Guidelines Dataset for RAG
GUIDELINES_DB = [
    {
        'title': 'Type 2 Diabetes Nutrition Guidelines (WHO)',
        'content': 'Nutrition for Type 2 Diabetes should focus on complex carbohydrates, high-fiber foods, and lean proteins. Limit refined sugars, sweetened beverages, and simple starches. Attaining consistent meal timing helps regulate blood glucose levels. Recommended: Whole grains, legumes, vegetables, and unsaturated fats.'
    },
    {
        'title': 'Hypertension and Sodium Restrictions (AHA/WHO)',
        'content': 'Hypertension guidelines strongly recommend adhering to the DASH (Dietary Approaches to Stop Hypertension) eating plan. Reduce sodium intake to less than 2,300 mg per day (ideally 1,500 mg). Include potassium-rich foods like bananas, spinach, and avocados. Limit processed foods, canned items, and cured meats.'
    },
    {
        'title': 'Chronic Disease Exercise & Activity Guidelines',
        'content': 'Chronic disease exercise standards state that patients should engage in at least 150 minutes of moderate-intensity aerobic exercise per week (e.g. brisk walking, cycling) spread over at least 3 days, with no more than 2 consecutive days without exercise. Include strength training twice weekly.'
    },
    {
        'title': 'High Cholesterol & Lipids Dietary Guidelines',
        'content': 'High Cholesterol guidelines focus on reducing saturated fats to less than 7% of total calories and eliminating trans fats. Eat foods rich in soluble fiber (oats, kidney beans, Brussels sprouts, pears) and omega-3 fatty acids (salmon, walnuts, flaxseeds) to improve LDL and HDL lipid profiles.'
    },
    {
        'title': 'Heart Disease and Lifestyle Management',
        'content': 'Heart Disease and Lifestyle management recommends stress reduction through mindfulness or light exercise. Ensure 7-9 hours of restful sleep daily. Avoid smoking and limit alcohol. Monitor blood pressure trends daily. Always consult your cardiologist before beginning high-intensity physical programs.'
    }
]

def get_relevant_document(query):
    """
    RAG Matcher: Uses Jaccard overlap on token sets of the query and the guidelines database
    to rank and retrieve the most relevant medical article.
    """
    query_tokens = set(re.findall(r'\w+', query.lower()))
    
    # Simple stop words to clean query
    stopwords = {'how', 'to', 'what', 'should', 'i', 'do', 'for', 'my', 'the', 'a', 'an', 'is', 'are', 'with', 'in', 'about'}
    query_tokens = query_tokens - stopwords
    
    if not query_tokens:
        return GUIDELINES_DB[2]  # Default to general exercise if query is empty
        
    best_doc = None
    best_score = -1.0
    
    for doc in GUIDELINES_DB:
        doc_tokens = set(re.findall(r'\w+', doc['content'].lower() + " " + doc['title'].lower()))
        doc_tokens = doc_tokens - stopwords
        
        # Calculate Jaccard similarity
        intersection = query_tokens.intersection(doc_tokens)
        union = query_tokens.union(doc_tokens)
        score = len(intersection) / len(union) if union else 0.0
        
        if score > best_score:
            best_score = score
            best_doc = doc
            
    return best_doc if best_score > 0 else GUIDELINES_DB[0]

def answer_patient_question(patient, question):
    """
    RAG Answering Engine: Finds relevant article, builds context prompt,
    calls Gemini API or uses fallback answers.
    """
    # 1. Retrieve context document via RAG
    relevant_doc = get_relevant_document(question)
    
    prompt = (
        "You are CareTrack AI, an educational healthcare assistant. You provide patient support "
        "and chronic disease education. You are talking to a patient.\n\n"
        "Here is the strict directive:\n"
        "1. Answer the patient's question based strictly on the clinical guidelines provided below.\n"
        "2. Keep the answer educational, helpful, and concise.\n"
        "3. NEVER diagnose the patient or prescribe medications/changes.\n"
        "4. Instruct the patient to consult their doctor before changing any care plan.\n"
        "5. Cite the source title of the guidelines at the end of the answer.\n\n"
        f"Medical Guidelines Context:\n{relevant_doc['content']}\n\n"
        f"Patient Question:\n{question}"
    )
    
    api_key = current_app.config.get('GEMINI_API_KEY')
    if api_key:
        try:
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel('gemini-1.5-flash')
            response = model.generate_content(prompt)
            return response.text.strip()
        except Exception as e:
            current_app.logger.error(f"Gemini RAG call failed: {str(e)}. Using fallback response.")
            
    # Fallback response
    doctor_name = "your physician"
    if patient.doctors:
        doctor_name = f"Dr. {patient.doctors[0].name}"
        
    fallback_answer = (
        f"### Educational Information\n"
        f"{relevant_doc['content']}\n\n"
        f"**Source Citation:** *{relevant_doc['title']}*\n\n"
        f"--- \n"
        f"> **Safety Recommendation:** This information is educational. "
        f"Please consult {doctor_name} before adjusting your medications, diet, or exercise routines."
    )
    return fallback_answer

