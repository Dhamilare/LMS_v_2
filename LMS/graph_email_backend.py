import requests
import json
import base64
from django.core.mail.backends.base import BaseEmailBackend
from django.conf import settings
from msal import ConfidentialClientApplication
from urllib.parse import quote


class GraphEmailBackend(BaseEmailBackend):
    def __init__(self, fail_silently=False, **kwargs):
        super().__init__(fail_silently=fail_silently)

        self.client_id = settings.SOCIAL_AUTH_AZUREAD_OAUTH2_KEY
        self.client_secret = settings.SOCIAL_AUTH_AZUREAD_OAUTH2_SECRET
        self.tenant_id = settings.SOCIAL_AUTH_AZUREAD_OAUTH2_TENANT_ID

        raw_sender = settings.EMAIL_SENDER or ""
        self.sender_email = raw_sender.strip()

        self.authority = f"https://login.microsoftonline.com/{self.tenant_id}"
        self.scope = ["https://graph.microsoft.com/.default"]

        self.app = ConfidentialClientApplication(
            self.client_id,
            authority=self.authority,
            client_credential=self.client_secret
        )

        self.encoded_sender_email = quote(self.sender_email)

    def get_access_token(self):
        result = self.app.acquire_token_silent(self.scope, account=None)
        if not result:
            result = self.app.acquire_token_for_client(scopes=self.scope)

        if "access_token" not in result:
            raise Exception("Failed to acquire access token from Microsoft Graph API.")
        return result["access_token"]

    def send_messages(self, email_messages):
        access_token = self.get_access_token()

        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }

        num_sent = 0

        for email_message in email_messages:

            # Recipients
            recipients = [
                {"emailAddress": {"address": email}}
                for email in email_message.to
            ]

            # Attachments
            attachments_list = []
            for attachment in email_message.attachments:
                filename, content, mimetype = attachment
                base64_content = base64.b64encode(content).decode("utf-8")

                attachments_list.append({
                    "@odata.type": "#microsoft.graph.fileAttachment",
                    "name": filename,
                    "contentType": mimetype,
                    "contentBytes": base64_content,
                    "isInline": False
                })

            # Message body
            message = {
                "subject": email_message.subject,
                "body": {
                    "contentType": "HTML",
                    "content": email_message.body
                },
                "toRecipients": recipients,
                "attachments": attachments_list
            }

            payload = {
                "message": message,
                "saveToSentItems": True
            }

            send_mail_url = (
                f"https://graph.microsoft.com/v1.0/users/"
                f"{self.encoded_sender_email}/sendMail"
            )

            try:
                response = requests.post(
                    send_mail_url,
                    headers=headers,
                    data=json.dumps(payload),
                    timeout=30
                )

                if response.status_code == 202:
                    num_sent += 1
                else:
                    print(f"Graph API Mail Send Failure (Status {response.status_code})")
                    print(f"URL: {send_mail_url}")
                    print(f"Response: {response.text}")
                    raise Exception(
                        f"Graph API error {response.status_code}: {response.text}"
                    )

            except Exception as e:
                if not self.fail_silently:
                    raise e

        return num_sent
