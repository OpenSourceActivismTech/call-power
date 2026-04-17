from requests_toolbelt import sessions

from callpower.crm_sync.integrations.base import CRMIntegration


class RogueIntegration(CRMIntegration):
    def __init__(self, domain, api_key):
        if not domain or not api_key:
            raise ValueError("ROGUE_DOMAIN and ROGUE_API_KEY are required")
        super().__init__()
        self.rogue_session = sessions.BaseUrlSession(base_url=f"https://{domain}")
        self.rogue_session.headers = {
            "X-DS-Importer-API-Key": api_key,
            "Accept": "application/json",
        }

    def get_user(self, phone_number):
        return {"id": phone_number, "phone": phone_number}

    def save_action(self, call, crm_campaign_id, crm_user, crm_campaign_key=None):
        call_action = {
            "mobile": crm_user["phone"],
            "callpower_campaign_id": call.campaign.id,
            "status": call.status,
            "call_timestamp": call.timestamp.isoformat() if call.timestamp else "",
            "call_duration": call.duration,
            "campaign_target_name": call.target.name if call.target else "",
            "campaign_target_title": call.target.title if call.target else "",
            "campaign_target_district": call.target.district if call.target else "",
            "callpower_campaign_name": call.campaign.name if call.campaign else "",
            "number_dialed_into": call.session.from_number if call.session else "",
        }
        response = self.rogue_session.post("/api/v1/callpower/call", json=call_action)
        return response.ok, response.text

    def save_campaign_meta(self, crm_campaign_id, meta):
        raise NotImplementedError()
