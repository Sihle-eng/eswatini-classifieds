import os
import requests
from flask import render_template, current_app, url_for
from datetime import datetime
from queue import Queue
from threading import Thread
import time

# Global queue and worker flag
_email_queue = Queue()
_worker_running = False

def _process_email_queue():
    """
    Background worker that processes email jobs from the queue.
    """
    global _worker_running
    while _worker_running:
        try:
            job = _email_queue.get(timeout=2)
            if job is None:
                continue
            to, subject, template_name, kwargs = job
            _send_email_job(to, subject, template_name, **kwargs)
        except Queue.Empty:
            continue
        except Exception as e:
            print(f"[ERROR] Queue worker error: {e}")

def _send_email_job(to, subject, template_name, **kwargs):
    """
    Actual sending logic – reusable.
    """
    # Use os.environ directly instead of current_app.config
    api_key = os.environ.get('BREVO_API_KEY')
    if not api_key:
        raise ValueError("BREVO_API_KEY not configured in environment")

    # We still need app context for rendering templates and URL building
    from app import create_app
    app = create_app()
    with app.app_context():
        try:
            html_content = render_template(f'emails/{template_name}.html', **kwargs)
            sender_email = current_app.config.get('MAIL_DEFAULT_SENDER')
            
            url = "https://api.brevo.com/v3/smtp/email"
            headers = {
                "api-key": api_key,
                "Content-Type": "application/json",
                "Accept": "application/json"
            }
            payload = {
                "sender": {"email": sender_email},
                "to": [{"email": to}],
                "subject": subject,
                "htmlContent": html_content
            }

            # Debug prints (remove after fixed)
            print(f"[DEBUG] Using api_key: {api_key[:10]}... (length {len(api_key)})")
            print(f"[DEBUG] Sender: {sender_email}, To: {to}")

            for attempt in range(2):
                try:
                    response = requests.post(url, json=payload, headers=headers, timeout=10)
                    response.raise_for_status()
                    print(f"[SUCCESS] Email sent to {to}: {subject}")
                    return
                except requests.exceptions.Timeout:
                    if attempt == 0:
                        print(f"[WARN] Timeout on attempt 1 for {to}, retrying...")
                        time.sleep(2)
                    else:
                        raise
                except Exception as e:
                    if attempt == 0:
                        if hasattr(e, 'response') and e.response is not None:
                            print(f"[WARN] Error on attempt 1: {e}, body: {e.response.text}")
                        else:
                            print(f"[WARN] Error on attempt 1: {e}, retrying...")
                        time.sleep(2)
                    else:
                        raise
        except Exception as e:
            print(f"[ERROR] Failed to send email to {to}: {e}")

def start_email_worker():
    """
    Start the background queue worker.
    Call this once when the Flask app starts.
    """
    global _worker_running
    if not _worker_running:
        _worker_running = True
        worker_thread = Thread(target=_process_email_queue, daemon=True)
        worker_thread.start()
        print("[INFO] Email queue worker started")

def send_email_async(to, subject, template_name, **kwargs):
    """
    Non‑blocking email send – puts the job in the queue.
    """
    _email_queue.put((to, subject, template_name, kwargs))
    print(f"[INFO] Email queued to {to}: {subject}")
    return True

def send_email(to, subject, template_name, **kwargs):
    """Async email send (compatible with old code)."""
    return send_email_async(to, subject, template_name, **kwargs)

# ------------------------------------------------------------
# Wrapper functions (unchanged from your original code)
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