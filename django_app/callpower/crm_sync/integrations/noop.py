from callpower.crm_sync.integrations.base import CRMIntegration


class NoOpIntegration(CRMIntegration):
    def __init__(self, default_phone=None):
        self.default_phone = default_phone or "+15555550199"

    def get_phone(self, twilio_sid):
        return self.default_phone

    def get_user(self, phone_number):
        return {"id": phone_number, "phone": phone_number, "email": "noop@example.com"}

    def save_action(self, call, crm_campaign_id, crm_user, crm_campaign_key=None):
        return True, f"noop sync for campaign {crm_campaign_id}"

    def save_campaign_meta(self, crm_campaign_id, meta):
        return True
