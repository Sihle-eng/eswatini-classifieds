# File: app/email_utils.py

import threading
import socket
from flask import render_template, current_app, url_for
from flask_mail import Message
from app import mail
from datetime import datetime
import os
import uuid

def _send_email_thread(app, msg):
    """Send email in a background thread (handles its own app context)."""
    with app.app_context():
        # Set a short socket timeout so the thread doesn't hang forever
        original_timeout = socket.getdefaulttimeout()
        socket.setdefaulttimeout(15.0)   # 15 seconds connect/read timeout
        try:
            mail.send(msg)
            print(f"[SUCCESS] Background email sent to {msg.recipients}")
        except Exception as e:
            print(f"[ERROR] Background email failed: {e}")
        finally:
            socket.setdefaulttimeout(original_timeout)

def send_email_async(to, subject, template_name, **kwargs):
    """Non‑blocking email send: returns immediately, sends in background."""
    try:
        html_content = render_template(f'emails/{template_name}.html', **kwargs)
        msg = Message(
            subject=subject,
            recipients=[to],
            html=html_content,
            sender=current_app.config['MAIL_DEFAULT_SENDER']
        )
        # Get a reference to the current app (for the background thread)
        app = current_app._get_current_object()
        thread = threading.Thread(target=_send_email_thread, args=(app, msg))
        thread.daemon = True
        thread.start()
        print(f"[INFO] Email queued to {to}: {subject}")
        return True
    except Exception as e:
        print(f"[ERROR] Failed to queue email: {e}")
        return False

# Keep your original send_email for compatibility, but make it use the async version
def send_email(to, subject, template_name, **kwargs):
    """Now non‑blocking by default (uses background thread)."""
    return send_email_async(to, subject, template_name, **kwargs)


# ------------------------------------------------------------
# Your existing wrapper functions (unchanged)
# ------------------------------------------------------------

def send_welcome_email(user_email, user_type, name):
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