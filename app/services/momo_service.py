import os
import requests
import base64
from flask import current_app


class MTNMoMoService:
    """MTN Mobile Money API Service for Eswatini"""
    
    def __init__(self):
        self.base_url = "https://sandbox.momodeveloper.mtn.com"
        self.api_key = os.environ.get('MTN_MOMO_API_KEY')
        self.api_user = os.environ.get('MTN_MOMO_API_USER')
        self.subscription_key = os.environ.get('MTN_MOMO_SUBSCRIPTION_KEY')
        self.callback_url = os.environ.get('MTN_MOMO_CALLBACK_URL')
        self.currency = os.environ.get('MTN_MOMO_CURRENCY', 'SZL')
        
        print(f"🔧 MoMo Service Initialized:")
        print(f"   API User: {self.api_user}")
        print(f"   API Key: {self.api_key[:10] if self.api_key else 'None'}...")
        print(f"   Subscription: {self.subscription_key[:10] if self.subscription_key else 'None'}...")
    
    def get_access_token(self):
        """Get OAuth 2.0 access token for API calls"""
        auth_string = f"{self.api_user}:{self.api_key}"
        encoded_auth = base64.b64encode(auth_string.encode()).decode()
        
        headers = {
            "Authorization": f"Basic {encoded_auth}",
            "Ocp-Apim-Subscription-Key": self.subscription_key
        }
        
        print(f"🔑 Requesting token from: {self.base_url}/collection/token/")
        
        try:
            response = requests.post(
                f"{self.base_url}/collection/token/",
                headers=headers,
                data={"grant_type": "client_credentials"},
                timeout=10
            )
            
            print(f"📡 Response Status: {response.status_code}")
            print(f"📄 Response Text: '{response.text}'")
            
            if response.status_code == 200:
                if response.text:
                    return response.json().get('access_token')
                else:
                    print("❌ Empty response body")
                    return None
            else:
                print(f"❌ HTTP Error {response.status_code}")
                return None
                
        except Exception as e:
            print(f"❌ Request failed: {e}")
            return None
    
    def request_to_pay(self, amount, phone_number, reference_id, message="Eswatini Classifieds - Ad Payment"):
        """Request payment from customer via USSD push"""
        print(f"📱 Requesting payment: SZL {amount} from {phone_number}")
        
        token = self.get_access_token()
        if not token:
            return False, "Could not get access token", None
        
        headers = {
            "Authorization": f"Bearer {token}",
            "X-Reference-Id": reference_id,
            "X-Target-Environment": "sandbox",
            "Ocp-Apim-Subscription-Key": self.subscription_key,
            "Content-Type": "application/json"
        }
        
        payload = {
            "amount": str(amount),
            "currency": self.currency,
            "externalId": reference_id,
            "payer": {
                "partyIdType": "MSISDN",
                "partyId": phone_number
            },
            "payerMessage": message,
            "payeeNote": f"Eswatini Classifieds - Ad #{reference_id[:8]}"
        }
        
        try:
            response = requests.post(
                f"{self.base_url}/collection/v1_0/requesttopay",
                headers=headers,
                json=payload,
                timeout=10
            )
            
            print(f"📡 RequestToPay Status: {response.status_code}")
            print(f"📄 Response: {response.text}")
            
            if response.status_code in [200, 202]:
                return True, "Payment request sent. Check your phone for USSD prompt.", reference_id
            return False, f"Payment request failed: {response.text}", None
            
        except Exception as e:
            return False, f"Request failed: {e}", None
    
    def get_payment_status(self, reference_id):
        """Check the status of a payment request"""
        token = self.get_access_token()
        if not token:
            return None
        
        headers = {
            "Authorization": f"Bearer {token}",
            "X-Target-Environment": "sandbox",
            "Ocp-Apim-Subscription-Key": self.subscription_key
        }
        
        try:
            response = requests.get(
                f"{self.base_url}/collection/v1_0/requesttopay/{reference_id}",
                headers=headers,
                timeout=10
            )
            
            if response.status_code == 200:
                return response.json()
            return None
            
        except Exception as e:
            print(f"❌ Status check failed: {e}")
            return None