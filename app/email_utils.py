
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
            # Get a job with a timeout (so the thread can check the flag)
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
    from app import create_app
    app = create_app()
    with app.app_context():
        try:
            api_key = current_app.config.get('BREVO_API_KEY')
            if not api_key:
                raise ValueError("BREVO_API_KEY not configured")

            html_content = render_template(f'emails/{template_name}.html', **kwargs)

            url = "https://api.brevo.com/v3/smtp/email"
            headers = {
                "api-key": api_key,
                "Content-Type": "application/json",
                "Accept": "application/json"
            }
            sender_email = current_app.config.get('MAIL_DEFAULT_SENDER')
            payload = {
                "sender": {"email": sender_email},
                "to": [{"email": to}],
                "subject": subject,
                "htmlContent": html_content
            }

            # Optional: print payload for debugging (remove after fixing)
            print(f"[DEBUG] Payload: {payload}")

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
                        # Enhanced: print the response body if available
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
    # Add job to the queue
    _email_queue.put((to, subject, template_name, kwargs))
    print(f"[INFO] Email queued to {to}: {subject}")
    return True

# ------------------------------------------------------------
# Backward compatibility wrappers (unchanged)
# ------------------------------------------------------------
def send_email(to, subject, template_name, **kwargs):
    return send_email_async(to, subject, template_name, **kwargs)

# ... keep all your existing wrapper functions exactly as they are ...
# (send_welcome_email, send_terms_agreement, etc.) – no changes needed.