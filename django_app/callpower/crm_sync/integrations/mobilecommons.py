from xml.etree import ElementTree

import dateutil.parser
from requests.auth import HTTPBasicAuth
from requests_toolbelt import sessions

from callpower.crm_sync.integrations.base import CRMIntegration


class MobileCommonsIntegration(CRMIntegration):
    BATCH_ALL_CALLS_IN_SESSION = True

    def __init__(self, username, password, company):
        if not username or not password:
            raise ValueError("MOBILE_COMMONS_USERNAME and MOBILE_COMMONS_PASSWORD are required")
        super().__init__()
        self.company = company
        self.mc_api = sessions.BaseUrlSession(base_url="https://secure.mcommons.com")
        self.mc_api.auth = HTTPBasicAuth(username, password)

    def get_user(self, phone_number):
        return {"id": phone_number, "phone": phone_number}

    def ok_to_subscribe_user(self, crm_campaign_id, crm_user):
        data = {
            "phone_number": crm_user["phone"],
            "company": self.company,
        }
        response = self.mc_api.get("/api/profile", params=data)
        try:
            results = ElementTree.fromstring(response.content)
        except ElementTree.ParseError:
            return False, "parse error"

        user_profile = results.find("profile")
        if user_profile is None:
            return True, None

        profile_subscriptions = user_profile.find("subscriptions")
        campaign_subscriptions = []
        for subscription in profile_subscriptions or []:
            if subscription.get("campaign_id") == crm_campaign_id:
                campaign_subscriptions.append(
                    {
                        "created_at": dateutil.parser.isoparse(subscription.get("created_at")),
                        "status": subscription.get("status"),
                    }
                )
        if not campaign_subscriptions:
            return True, None

        campaign_subscriptions.sort(key=lambda item: item["created_at"])
        most_recent = campaign_subscriptions[-1]
        if most_recent.get("status") == "Opted-Out":
            return False, "opted out"
        if most_recent.get("status") == "Active":
            return False, "already subscribed"
        return True, None

    def save_action(self, call, crm_campaign_id, crm_user, crm_campaign_key=None):
        ok, message = self.ok_to_subscribe_user(crm_campaign_id, crm_user)
        if not ok:
            return False, message

        data = {
            "phone_number": crm_user["phone"],
            "opt_in_path_id": crm_campaign_key,
            "company": self.company,
        }
        response = self.mc_api.post("/api/profile_update", data)
        try:
            results = ElementTree.fromstring(response.content)
        except ElementTree.ParseError:
            return False, "parse error"

        success = results.get("success") == "true"
        message = "" if success else (results.find("error").get("message") if results.find("error") is not None else "")
        return success, message

    def save_campaign_meta(self, crm_campaign_id, meta):
        raise NotImplementedError()
