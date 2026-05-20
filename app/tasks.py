import os
from flask import current_app
from datetime import datetime
from app.email_utils import send_email   # existing send_email (blocking version)

def send_welcome_email_job(user_email, user_type, name):
    """Enqueued job: send welcome email."""
    with current_app.app_context():
        login_url = current_app.config.get('SITE_URL', 'http://localhost:5000') + '/login'
        send_email(
            to=user_email,
            subject='Welcome to Eswatini Classifieds',
            template_name='welcome',
            user_type=user_type,
            name=name,
            login_url=login_url
        )

def send_terms_agreement_job(user_email, user_type, name, agreement_id, ip_address):
    """Enqueued job: send terms agreement email."""
    with current_app.app_context():
        date_signed = datetime.utcnow().strftime('%d %B %Y')
        send_email(
            to=user_email,
            subject='Terms & Conditions Agreement',
            template_name='terms_agreement',
            user_type=user_type,
            name=name,
            agreement_id=agreement_id,
            ip_address=ip_address,
            date_signed=date_signed
        )