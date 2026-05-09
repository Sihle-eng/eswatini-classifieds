# File: app/services/dodo_service.py

import os
import requests
import json
import hmac
import hashlib
from flask import current_app


class DodoPaymentsService:
    """Dodo Payments API Service"""
    
    def __init__(self):
        self.api_key = os.environ.get('DODO_API_KEY')
        self.webhook_secret = os.environ.get('DODO_WEBHOOK_SECRET')
        self.api_url = os.environ.get('DODO_API_URL', 'https://api.dodopayments.com/v1')
        self.enabled = os.environ.get('DODO_PAYMENTS_ENABLED', 'false').lower() == 'true'
        
    def create_payment_link(self, amount, currency, description, metadata=None):
        """
        Create a simple payment link for a fixed amount
        
        Args:
            amount: Amount in smallest currency unit (e.g., cents)
            currency: Currency code (e.g., 'SZL')
            description: Description of payment
            metadata: Dict of custom data (e.g., posting_id, user_id)
        """
        if not self.enabled:
            return {"success": False, "error": "Dodo Payments is not enabled"}
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "amount": int(amount * 100),  # Convert to cents
            "currency": currency,
            "description": description,
            "metadata": metadata or {}
        }
        
        try:
            response = requests.post(
                f"{self.api_url}/payment_links",
                headers=headers,
                json=payload,
                timeout=10
            )
            
            if response.status_code in [200, 201]:
                data = response.json()
                return {
                    "success": True,
                    "payment_link": data.get('url'),
                    "payment_id": data.get('id')
                }
            else:
                return {
                    "success": False,
                    "error": f"API Error: {response.text}"
                }
                
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def create_checkout_session(self, amount, currency, description, success_url, cancel_url, metadata=None):
        """
        Create a checkout session for embedded payment flow
        
        Args:
            amount: Amount in smallest currency unit (e.g., cents)
            currency: Currency code (e.g., 'SZL')
            description: Description of payment
            success_url: URL to redirect after successful payment
            cancel_url: URL to redirect after cancelled payment
            metadata: Dict of custom data (e.g., posting_id, user_id)
        """
        if not self.enabled:
            return {"success": False, "error": "Dodo Payments is not enabled"}
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "amount": int(amount * 100),
            "currency": currency,
            "description": description,
            "success_url": success_url,
            "cancel_url": cancel_url,
            "metadata": metadata or {}
        }
        
        try:
            response = requests.post(
                f"{self.api_url}/checkout/sessions",
                headers=headers,
                json=payload,
                timeout=10
            )
            
            if response.status_code in [200, 201]:
                data = response.json()
                return {
                    "success": True,
                    "checkout_url": data.get('url'),
                    "session_id": data.get('id')
                }
            else:
                return {
                    "success": False,
                    "error": f"API Error: {response.text}"
                }
                
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def verify_webhook_signature(self, payload, signature):
        """
        Verify that the webhook request came from Dodo Payments
        """
        if not self.webhook_secret:
            return False
        
        computed_signature = hmac.new(
            self.webhook_secret.encode('utf-8'),
            payload,
            hashlib.sha256
        ).hexdigest()
        
        return hmac.compare_digest(computed_signature, signature)