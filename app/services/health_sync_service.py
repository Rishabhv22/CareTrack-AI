import logging
from datetime import datetime, timedelta, date
from flask import request
from app.extensions import db
from app.models.patient import Patient
from app.models.wearable import WearableDevice
from app.models.recommendation import AuditLog
from app.services.wearable_service import MockHealthProvider
from app.services.health_data_service import add_health_metric
from app.services.health_summary_service import aggregate_daily_health_summary

logger = logging.getLogger(__name__)

def connect_wearable_provider(patient_id: str, provider: str, device_name: str, device_type: str) -> WearableDevice:
    """
    Connects a new wearable device/health platform to the patient profile.
    Requires patient consent to be true.
    """
    patient = db.session.get(Patient, patient_id)
    if not patient:
        raise ValueError("Patient not found.")
        
    if not patient.health_data_consent:
        raise ValueError("Cannot connect device: Health data synchronization consent is not granted.")
        
    # Check if a device for this provider already exists
    device = WearableDevice.query.filter_by(patient_id=patient_id, provider=provider).first()
    
    if not device:
        device = WearableDevice(
            patient_id=patient_id,
            provider=provider,
            device_name=device_name,
            device_type=device_type,
            connection_status='CONNECTED',
            connected_at=datetime.utcnow()
        )
        db.session.add(device)
    else:
        device.connection_status = 'CONNECTED'
        device.device_name = device_name
        device.device_type = device_type
        device.connected_at = datetime.utcnow()
        
    db.session.commit()
    
    # Audit logging
    audit = AuditLog(
        user_id=patient.user_id,
        action=f"CONNECT_WEARABLE provider={provider} device={device_name}",
        ip_address=request.remote_addr if request else '127.0.0.1'
    )
    db.session.add(audit)
    db.session.commit()
    
    return device


def disconnect_wearable_provider(patient_id: str, provider: str) -> bool:
    """
    Disconnects the wearable provider, stopping future synchronizations.
    """
    device = WearableDevice.query.filter_by(patient_id=patient_id, provider=provider).first()
    if not device:
        return False
        
    device.connection_status = 'DISCONNECTED'
    db.session.commit()
    
    patient = db.session.get(Patient, patient_id)
    
    # Audit logging
    audit = AuditLog(
        user_id=patient.user_id if patient else None,
        action=f"DISCONNECT_WEARABLE provider={provider}",
        ip_address=request.remote_addr if request else '127.0.0.1'
    )
    db.session.add(audit)
    db.session.commit()
    
    return True


def sync_patient_health_data(patient_id: str, days: int = 7) -> dict:
    """
    Orchestrates downloading, validating, storing, and summarizing wearable/health data.
    """
    patient = db.session.get(Patient, patient_id)
    if not patient:
        return {'success': False, 'error': 'Patient not found'}
        
    if not patient.health_data_consent:
        return {'success': False, 'error': 'Patient data sharing consent is revoked.'}
        
    # Get active connected device
    device = WearableDevice.query.filter_by(patient_id=patient_id, connection_status='CONNECTED').first()
    if not device:
        return {'success': False, 'error': 'No active connected wearable device found.'}
        
    today = datetime.utcnow().date()
    start_date = today - timedelta(days=days - 1)
    
    # 1. Fetch data from Mock Provider
    provider_inst = MockHealthProvider()
    
    try:
        metrics_list = provider_inst.fetch_health_data(
            start_date=start_date,
            end_date=today,
            patient_id=patient_id,
            primary_condition=patient.primary_condition,
            base_weight=patient.weight or 75.0
        )
        
        # 2. Store all metrics in database
        saved_count = 0
        for m in metrics_list:
            metric_obj = add_health_metric(
                patient_id=patient_id,
                device_id=device.id,
                metric_type=m['metric_type'],
                value=m['value'],
                unit=m['unit'],
                timestamp=m['timestamp'],
                source=m['source'],
                external_record_id=m['external_record_id']
            )
            if metric_obj:
                saved_count += 1
                
        # Update device last synced timestamp
        device.last_synced_at = datetime.utcnow()
        db.session.commit()
        
        # 3. Trigger daily health summary aggregations
        aggregate_daily_health_summary(patient_id, start_date, today)
        
        # Audit logging
        audit = AuditLog(
            user_id=patient.user_id,
            action=f"SYNC_WEARABLE_DATA patient_id={patient_id} provider={device.provider} metrics={saved_count}",
            ip_address=request.remote_addr if request else '127.0.0.1'
        )
        db.session.add(audit)
        db.session.commit()
        
        return {
            'success': True,
            'metrics_synced': saved_count,
            'last_sync': device.last_synced_at.strftime('%Y-%m-%d %H:%M:%S')
        }
        
    except Exception as e:
        logger.error(f"Synchronization failed for patient {patient_id}: {str(e)}")
        return {'success': False, 'error': f"Sync failed: {str(e)}"}
