from twilio.base.exceptions import TwilioRestException

from callpower.apps.calls.views import twilio_client


class CRMIntegration:
    BATCH_ALL_CALLS_IN_SESSION = False

    def __init__(self):
        self.twilio_client = twilio_client()

    def get_phone(self, twilio_sid):
        twilio_call = self.twilio_client.calls(twilio_sid).fetch()
        direction = getattr(twilio_call, "direction", "") or ""
        if direction == "inbound":
            return twilio_call.from_
        if direction.startswith("outbound"):
            return twilio_call.to
        return None

    def get_user(self, phone_number):
        raise NotImplementedError()

    def save_action(self, call, crm_campaign_id, crm_user, crm_campaign_key=None):
        raise NotImplementedError()

    def save_campaign_meta(self, crm_campaign_id, meta):
        raise NotImplementedError()


class CRMIntegrationError(Exception):
    pass


def safe_twilio_lookup(integration, twilio_sid):
    try:
        return integration.get_phone(twilio_sid)
    except TwilioRestException as exc:
        raise CRMIntegrationError(str(exc)) from exc
