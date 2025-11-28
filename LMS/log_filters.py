import logging

class SensitiveURLFilter(logging.Filter):
    """
    Filters out log records containing sensitive OAuth callback URLs.
    """
    def filter(self, record):
        if '/auth/complete/azuread-oauth2/' in record.getMessage():
            return False  # Do NOT log this request
        
        return True # Log everything else