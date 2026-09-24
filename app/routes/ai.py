from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from app.services.ai_service import answer_patient_question

ai_bp = Blueprint('ai', __name__)

@ai_bp.route('/chat')
@login_required
def chat():
    if current_user.role != 'PATIENT':
        flash('Access denied.', 'danger')
        return redirect(url_for('index'))
        
    patient = current_user.patient_profile
    if not patient:
        flash('Please complete your profile first.', 'warning')
        return redirect(url_for('patient.create_profile'))
        
    return render_template('patient/ai_chat.html', patient=patient)

@ai_bp.route('/chat/send', methods=['POST'])
@login_required
def chat_send():
    if current_user.role != 'PATIENT':
        return jsonify({'error': 'Unauthorized'}), 403
        
    patient = current_user.patient_profile
    data = request.get_json() or {}
    message = data.get('message', '').strip()
    
    if not message:
        return jsonify({'error': 'Message content cannot be empty'}), 400
        
    # Get response using RAG + Gemini/fallback
    answer = answer_patient_question(patient, message)
    
    return jsonify({'answer': answer})
