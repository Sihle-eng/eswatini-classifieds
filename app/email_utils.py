# File: app/email_utils.py

from flask import render_template, current_app, url_for
from flask_mail import Message
from app import mail
from datetime import datetime
import os
import uuid


def send_email(to, subject, template_name, **kwargs):
    """Generic email sending function -FIXED VERSION MAY 10"""
    try:
        html_content = render_template(f'emails/{template_name}.html', **kwargs)
        
        msg = Message(
            subject=subject,
            recipients=[to],
            html=html_content,
            sender=current_app.config['MAIL_DEFAULT_SENDER']
        )
        
        # Try to actually send, but don't crash if SMTP fails
        try:
            mail.send(msg)
            print(f"[SUCCESS] Email sent to {to}: {subject}")
        except Exception as send_error:
            print(f"[WARNING] SMTP send failed (non-blocking): {send_error}")
            print(f"[INFO] Registration continues. Would have sent to {to}: {subject}")
        
        return True
    except Exception as e:
        print(f"[ERROR] Email template error: {e}")
        return False

def send_welcome_email(user_email, user_type, name):
    """Send welcome email after registration"""
    subject = f'Welcome to Eswatini Classifieds, {name}!'
    
    return send_email(
        to=user_email,
        subject=subject,
        template_name='welcome',
        user_name=name,
        user_type=user_type,
        user_email=user_email,
        login_url=current_app.config.get('SITE_URL', 'http://localhost:5000') + url_for('main.login')
    )


def send_terms_agreement(user_email, user_type, name, agreement_id, ip_address):
    """Send Terms & Conditions agreement copy"""
    subject = 'Your Terms & Conditions Agreement - Eswatini Classifieds'
    
    return send_email(
        to=user_email,
        subject=subject,
        template_name='terms_agreement',
        user_name=name,
        user_type=user_type,
        user_email=user_email,
        agreement_id=agreement_id,
        ip_address=ip_address,
        date_signed=datetime.utcnow().strftime('%d %B %Y'),
        site_url=current_app.config.get('SITE_URL', 'http://localhost:5000')
    )


def send_ad_posted_confirmation(user_email, ad_title, ad_id, expires_at, amount, payment_method):
    """Send confirmation when ad is posted"""
    subject = f'Your ad "{ad_title}" is now live!'
    
    site_url = current_app.config.get('SITE_URL', 'http://localhost:5000')
    
    return send_email(
        to=user_email,
        subject=subject,
        template_name='ad_confirmation',
        ad_title=ad_title,
        ad_id=ad_id,
        expires_at=expires_at,
        amount=amount,
        payment_method=payment_method,
        ad_url=site_url + url_for('main.view_ad', posting_id=ad_id),
        dashboard_url=site_url + url_for('main.my_ads')
    )


def send_ad_expiry_reminder(user_email, ad_title, expires_at, ad_id):
    """Send reminder when ad is about to expire"""
    subject = f'Your ad "{ad_title}" expires soon!'
    
    site_url = current_app.config.get('SITE_URL', 'http://localhost:5000')
    
    return send_email(
        to=user_email,
        subject=subject,
        template_name='expiry_reminder',
        ad_title=ad_title,
        expires_at=expires_at,
        ad_id=ad_id,
        renew_url=site_url + url_for('main.renew_ad', posting_id=ad_id)
    )


def send_payment_confirmation(user_email, ad_title, amount, payment_method, transaction_id):
    """Send payment confirmation"""
    subject = f'Payment Confirmed - {ad_title}'
    
    site_url = current_app.config.get('SITE_URL', 'http://localhost:5000')
    
    return send_email(
        to=user_email,
        subject=subject,
        template_name='payment_confirmation',
        ad_title=ad_title,
        amount=amount,
        payment_method=payment_method,
        transaction_id=transaction_id,
        dashboard_url=site_url + url_for('main.my_ads')
    )


def send_contact_inquiry(seller_email, seller_name, buyer_name, buyer_email, buyer_phone, message, ad_title, ad_id):
    """Forward contact inquiry to seller"""
    subject = f'New Inquiry: {ad_title}'
    
    site_url = current_app.config.get('SITE_URL', 'http://localhost:5000')
    
    return send_email(
        to=seller_email,
        subject=subject,
        template_name='contact_inquiry',
        seller_name=seller_name,
        buyer_name=buyer_name,
        buyer_email=buyer_email,
        buyer_phone=buyer_phone,
        message=message,
        ad_title=ad_title,
        ad_url=site_url + url_for('main.view_ad', posting_id=ad_id)
    )


def send_password_reset(user_email, reset_token):
    """Send password reset email"""
    subject = 'Password Reset Request - Eswatini Classifieds'
    
    site_url = current_app.config.get('SITE_URL', 'http://localhost:5000')
    reset_url = site_url + url_for('main.reset_password', token=reset_token)
    
    return send_email(
        to=user_email,
        subject=subject,
        template_name='password_reset',
        reset_url=reset_url,
        user_email=user_email
    )