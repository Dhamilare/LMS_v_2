import requests
from msal import ConfidentialClientApplication
from django.core.mail.backends.base import BaseEmailBackend
from decouple import config

class GraphEmailBackend(BaseEmailBackend):
    
    def __init__(self, fail_silently=False, **kwargs):
        super().__init__(fail_silently=fail_silently)
        self.client_id = config('SOCIAL_AUTH_AZUREAD_OAUTH2_KEY')
        self.client_secret = config('SOCIAL_AUTH_AZUREAD_OAUTH2_SECRET')
        self.tenant_id = config('SOCIAL_AUTH_AZUREAD_OAUTH2_TENANT_ID')
        self.email_sender = config('EMAIL_SENDER')
        
        if not all([self.client_id, self.client_secret, self.tenant_id, self.email_sender]):
            raise ValueError("Email backend is missing required settings (KEY, SECRET, TENANT_ID, or EMAIL_SENDER).")
            
        self.authority = f"https://login.microsoftonline.com/{self.tenant_id}"
        self.scope = ["https://graph.microsoft.com/.default"]
        
        self.client_app = ConfidentialClientApplication(
            client_id=self.client_id,
            authority=self.authority,
            client_credential=self.client_secret
        )

    def _get_access_token(self):
        """
        Get an app-only access token from MSAL.
        It will first try the cache, then acquire a new one if needed.
        """
        result = self.client_app.acquire_token_silent(scopes=self.scope, account=None)
        
        if not result:
            print("No token in cache, acquiring new one...")
            result = self.client_app.acquire_token_for_client(scopes=self.scope)
            
        if "access_token" in result:
            return result["access_token"]
        else:
            print(f"Error acquiring token: {result.get('error_description')}")
            return None

    def send_messages(self, email_messages):
        """
        Sends one or more EmailMessage objects.
        Returns the number of messages sent.
        """
        if not email_messages:
            return 0
            
        access_token = self._get_access_token()
        if not access_token:
            if not self.fail_silently:
                raise Exception("Failed to acquire Graph API access token.")
            return 0

        headers = {
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json'
        }
        
        send_count = 0
        for message in email_messages:
            # Construct the API payload
            graph_message = {
                "message": {
                    "from": {
                        "emailAddress": {
                            "address": self.email_sender
                        }
                    },
                    "toRecipients": [
                        {"emailAddress": {"address": to}} for to in message.to
                    ],
                    "subject": message.subject,
                    "body": {
                        "contentType": "Html" if message.content_subtype == "html" else "Text",
                        "content": message.body
                    }
                },
                "saveToSentItems": "true"
            }
            
            # Add CC and BCC recipients if they exist
            if message.cc:
                graph_message["message"]["ccRecipients"] = [
                    {"emailAddress": {"address": cc}} for cc in message.cc
                ]
            if message.bcc:
                graph_message["message"]["bccRecipients"] = [
                    {"emailAddress": {"address": bcc}} for bcc in message.bcc
                ]
            
            # The API endpoint to send mail FROM a specific user (our service account)
            send_mail_url = f"https://graph.microsoft.com/v1.0/users/{self.email_sender}/sendMail"
            
            try:
                response = requests.post(
                    send_mail_url,
                    headers=headers,
                    json=graph_message
                )
            
                if response.status_code == 202:  # 202 Accepted
                    send_count += 1
                else:
                    if not self.fail_silently:
                        raise Exception(
                            f"Graph API error {response.status_code}: {response.text}"
                        )
            except Exception as e:
                if not self.fail_silently:
                    raise e

        return send_count