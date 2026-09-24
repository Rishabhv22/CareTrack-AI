import logging
import spacy
import re

logger = logging.getLogger(__name__)

# Load spaCy model with dynamic download fallback
_nlp = None
def get_spacy_nlp():
    global _nlp
    if _nlp is not None:
        return _nlp
        
    try:
        _nlp = spacy.load("en_core_web_sm")
    except OSError:
        logger.info("Downloading en_core_web_sm spaCy model...")
        try:
            from spacy.cli import download
            download("en_core_web_sm")
            _nlp = spacy.load("en_core_web_sm")
        except Exception as e:
            logger.warning(f"Could not download en_core_web_sm: {str(e)}. Falling back to rule-based NLP.")
            _nlp = None
    return _nlp

def analyze_journal(journal_text):
    """
    Upgraded NLP Journal Service.
    Uses spaCy for dependency-based negation checks and sentence analysis.
    Falls back to a keyword-matching model if spaCy is unavailable.
    """
    if not journal_text:
        return {
            "summary": "",
            "symptoms": [],
            "medications": "No logs",
            "diet_activity": "No logs",
            "concerning_flag": False
        }
        
    nlp_model = get_spacy_nlp()
    text_lower = journal_text.lower()
    
    # 1. Symptom list & triggers
    symptom_map = {
        'fatigue': ['tired', 'fatigue', 'exhausted', 'sleepy', 'weak', 'lethargic', 'low energy'],
        'pain': ['pain', 'ache', 'sore', 'hurt', 'cramps'],
        'dizziness': ['dizzy', 'dizziness', 'lightheaded', 'spinning', 'unsteady'],
        'headache': ['headache', 'migraine', 'head ache'],
        'nausea': ['nausea', 'vomit', 'sick to stomach', 'throwing up'],
        'shortness of breath': ['breathless', 'shortness of breath', 'gasping', 'hard to breathe']
    }
    
    symptoms_found = []
    
    # Negation check helper
    def is_negated(token):
        """
        Check if a token has a negation child (e.g. 'not', 'no', 'never') in the dependency tree.
        """
        for child in token.children:
            if child.dep_ == 'neg' or child.lemma_ in ['no', 'not', 'never', 'nothing']:
                return True
        # Check parents for negation if relevant
        if token.head and token.head.lemma_ in ['no', 'not', 'never']:
            return True
        return False

    if nlp_model:
        # Load text in spaCy
        doc = nlp_model(journal_text)
        
        # Check symptoms
        for sentence in doc.sents:
            sent_text = sentence.text.lower()
            for symptom, keywords in symptom_map.items():
                for kw in keywords:
                    if kw in sent_text:
                        # Find the token corresponding to the keyword to check negation
                        matched_token = None
                        for token in sentence:
                            if token.text.lower() == kw or token.lemma_.lower() == kw or kw in token.text.lower():
                                matched_token = token
                                break
                        
                        if matched_token and is_negated(matched_token):
                            # Symptom is negated, e.g. "I do not have pain" -> skip
                            continue
                        else:
                            if symptom not in symptoms_found:
                                symptoms_found.append(symptom)
    else:
        # Fallback to rule-based keyword check
        for symptom, keywords in symptom_map.items():
            if any(keyword in text_lower for keyword in keywords):
                # Basic check for negation patterns right before keyword
                negated = False
                for neg in ['no ', 'not ', 'never ', 'without ']:
                    pos = text_lower.find(neg)
                    if pos != -1:
                        kw_pos = any(text_lower.find(k) for k in keywords)
                        if abs(pos - kw_pos) < 15:
                            negated = True
                            break
                if not negated:
                    symptoms_found.append(symptom)

    # 2. Medication Compliance Mentions with negation check
    med_status = "Not mentioned"
    
    # Regex helper for fallback/keyword matching
    took_regex = r'\b(took|take|taken)\s+(?:my\s+)?(?:diabetes\s+|blood\s+pressure\s+)?(medicine|medication|pill|dose|insulin|meds)\b'
    miss_keywords = ['skipped', 'missed', 'forgot my medicine', 'forgot my pill', 'forgot med', 'missed dose', 'forgot medication']
    
    if nlp_model:
        doc = nlp_model(journal_text)
        for token in doc:
            if token.lemma_ == 'take':
                for child in token.children:
                    if child.lemma_ in ['medicine', 'medication', 'pill', 'dose', 'insulin', 'meds']:
                        if is_negated(token) or is_negated(child):
                            med_status = "Medication Missed"
                        else:
                            med_status = "Medication Taken"
                        break
                if med_status != "Not mentioned":
                    break
                    
        # Double check with regex/keywords if still undecided
        if med_status == "Not mentioned":
            if re.search(took_regex, text_lower):
                med_status = "Medication Taken"
            elif any(k in text_lower for k in miss_keywords):
                med_status = "Medication Missed"
    else:
        # Fallback to regex and keyword searches
        if re.search(took_regex, text_lower):
            med_status = "Medication Taken"
        elif any(k in text_lower for k in miss_keywords):
            med_status = "Medication Missed"

    # 3. Diet and Activity Mentions
    activities = []
    if any(k in text_lower for k in ['walk', 'walked', 'walking']):
        activities.append("Walking")
    if any(k in text_lower for k in ['run', 'running', 'jog', 'jogging']):
        activities.append("Running")
    if any(k in text_lower for k in ['gym', 'workout', 'exercise', 'active']):
        activities.append("General Exercise")
        
    diet_mentions = []
    if any(k in text_lower for k in ['skipped breakfast', 'skipped lunch', 'skipped dinner']):
        diet_mentions.append("Skipped meal")
    if any(k in text_lower for k in ['healthy diet', 'clean eating', 'followed diet', 'low carb']):
        diet_mentions.append("Diet followed")
        
    diet_activity_summary = ", ".join(activities + diet_mentions) if (activities or diet_mentions) else "Not mentioned"
    
    # 4. Concern Flag (Critical alerts)
    concerning_flag = False
    concern_keywords = ['chest pain', 'severe pain', 'extreme dizzy', 'breathless', 'blacked out', 'fainted']
    if any(k in text_lower for k in concern_keywords):
        concerning_flag = True

    # 5. Summary Generation
    summary_parts = []
    if symptoms_found:
        summary_parts.append(f"Symptoms reported: {', '.join(symptoms_found)}.")
    else:
        summary_parts.append("No critical symptoms reported.")
        
    if med_status != "Not mentioned":
        summary_parts.append(f"{med_status}.")
        
    if diet_activity_summary != "Not mentioned":
        summary_parts.append(f"Lifestyle: {diet_activity_summary}.")
        
    summary = " ".join(summary_parts)
    
    return {
        "summary": summary,
        "symptoms": symptoms_found,
        "medications": med_status,
        "diet_activity": diet_activity_summary,
        "concerning_flag": concerning_flag
    }
