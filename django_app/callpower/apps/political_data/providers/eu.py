from callpower.apps.political_data.providers.base import CampaignType, DataProvider


class EUCampaignType(CampaignType):
    pass


class EUCampaignType_Custom(EUCampaignType):
    type_name = "Custom - MEP"


class EUDataProvider(DataProvider):
    campaign_types = [("custom", EUCampaignType_Custom)]

    def load_data(self):
        return 0


class FRDataProvider(EUDataProvider):
    country_name = "France"
    country_code = "fr"


class DEDataProvider(EUDataProvider):
    country_name = "Germany"
    country_code = "de"


class ESDataProvider(EUDataProvider):
    country_name = "Spain"
    country_code = "es"


class IRDataProvider(EUDataProvider):
    country_name = "Ireland"
    country_code = "ir"


class ITDataProvider(EUDataProvider):
    country_name = "Italy"
    country_code = "it"


class PLDataProvider(EUDataProvider):
    country_name = "Poland"
    country_code = "pl"


class UKDataProvider(EUDataProvider):
    country_name = "United Kingdom"
    country_code = "uk"
