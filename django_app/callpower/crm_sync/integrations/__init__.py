from django.conf import settings

from callpower.crm_sync.integrations.base import CRMIntegrationError


def get_crm_integration():
    integration_name = (settings.CRM_INTEGRATION or "").strip().lower()
    if not integration_name:
        raise CRMIntegrationError("no CRM_INTEGRATION configured")

    if integration_name == "actionkit":
        from callpower.crm_sync.integrations.actionkit import ActionKitIntegration

        return ActionKitIntegration(
            domain=settings.ACTIONKIT_DOMAIN,
            username=settings.ACTIONKIT_USER,
            api_key=settings.ACTIONKIT_API_KEY,
            password=settings.ACTIONKIT_PASSWORD,
        )

    if integration_name == "rogue":
        from callpower.crm_sync.integrations.rogue import RogueIntegration

        return RogueIntegration(domain=settings.ROGUE_DOMAIN, api_key=settings.ROGUE_API_KEY)

    if integration_name == "mobilecommons":
        from callpower.crm_sync.integrations.mobilecommons import MobileCommonsIntegration

        return MobileCommonsIntegration(
            username=settings.MOBILE_COMMONS_USERNAME,
            password=settings.MOBILE_COMMONS_PASSWORD,
            company=settings.MOBILE_COMMONS_COMPANY,
        )

    if integration_name == "noop":
        from callpower.crm_sync.integrations.noop import NoOpIntegration

        return NoOpIntegration(default_phone=settings.CRM_DEBUG_PHONE)

    raise CRMIntegrationError(f"unknown CRM_INTEGRATION '{settings.CRM_INTEGRATION}'")
