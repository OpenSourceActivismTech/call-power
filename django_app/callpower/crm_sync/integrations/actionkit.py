import phonenumbers

from callpower.crm_sync.integrations.base import CRMIntegration


class ActionKitIntegration(CRMIntegration):
    def __init__(self, domain, username, api_key=None, password=None):
        try:
            from actionkit.rest import ActionKit
            from actionkit.xmlrpc import ActionKitXML
        except ImportError as exc:
            raise ImportError("python-actionkit is required for CRM_INTEGRATION=actionkit") from exc

        if not domain or not username or not (api_key or password):
            raise ValueError("ActionKit credentials are incomplete")

        super().__init__()
        if api_key:
            self.ak_client = ActionKit(instance=domain, username=username, api_key=api_key)
            self.ak_rpc = ActionKitXML(instance=domain, username=username, api_key=api_key)
        else:
            self.ak_client = ActionKit(instance=domain, username=username, password=password)
            self.ak_rpc = ActionKitXML(instance=domain, username=username, password=password)

    def get_user(self, phone_number):
        normalized_phone = phonenumbers.parse(phone_number).national_number
        matching_users = self.ak_client.phone.list(normalized_phone=normalized_phone)["objects"]
        if not matching_users:
            return None
        user_url = matching_users[0]["user"]
        ak_user = self.ak_client.get(user_url)
        ak_user["phone"] = str(normalized_phone)
        return ak_user

    def _match_target_data(self, call):
        campaign = call.campaign
        target = call.target
        target_type = "other"
        target_state = ""
        if campaign.country_code and campaign.country_code.upper() == "US":
            if campaign.campaign_type == "congress":
                target_state = (target.location or "").split()[-1] if target and target.location else ""
                if target and target.title == "Senator":
                    target_type = "senate"
                elif target and target.title == "Representative":
                    target_type = "house"
            elif target and target.title == "Governor":
                target_type = "governor"
        if campaign.country_code and campaign.country_code.upper() == "CA" and campaign.campaign_type == "lower":
            target_type = "parliament"
        return campaign.country_code, target_state, target_type, target.name

    def _get_target_id(self, country, state, target_type, target_name):
        target_data = {"country": country, "state": state, "type": target_type}
        ak_targets_list = self.ak_client.target.list(**target_data)["objects"]
        first_name, last_name = target_name.split(" ", 1)
        ak_target = next((target for target in ak_targets_list if target["last"] == last_name and target["first"] == first_name), None)
        if not ak_target:
            target_data["last"] = last_name
            target_data["first"] = first_name
            if target_type == "parliament":
                target_data["title"] = "MP"
            if target_type == "governor":
                target_data["title"] = "Governor"
            ak_target = self.ak_client.target.create(target_data)
        return ak_target["id"]

    def save_action(self, call, crm_campaign_id, crm_user, crm_campaign_key=None):
        crm_target_id = self._get_target_id(*self._match_target_data(call))
        call_action = {
            "email": crm_user["email"],
            "phone": crm_user["phone"],
            "page": crm_campaign_id,
            "source": "CallPower CRMSync",
            "target_checked": crm_target_id,
            "action_duration": call.duration,
            "action_status": call.status,
            "skip_confirmation": 1,
        }
        result = self.ak_client.action.create(call_action)
        return True, result.get("status")

    def save_campaign_meta(self, crm_campaign_id, meta):
        response = self.ak_client.get("/rest/v1/page/", params={"name": crm_campaign_id})
        campaign_page = response["objects"][0]
        page_custom_fields = {"id": campaign_page["id"]}
        for key, value in meta.items():
            page_custom_fields[f"callpower_{key}"] = value
        result = self.ak_rpc.Page.set_custom_fields(page_custom_fields)
        last_key = f"callpower_{list(meta.keys())[-1]}" if meta else None
        return bool(last_key and result.get(last_key) == meta[list(meta.keys())[-1]])
