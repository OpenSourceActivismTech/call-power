import os

import geopy

from callpower.apps.political_data.constants import CA_PROVINCE_NAME_DICT, US_STATE_NAME_DICT


GOOGLE_SERVICE = "GoogleV3"
SMARTYSTREETS_SERVICE = "LiveAddress"
SMARTYSTEETS_ZIPCODE_SERVICE = "SmartyStreetsUSZipcode"
NOMINATIM_SERVICE = "Nominatim"
LOCAL_USDATA_SERVICE = "LocalUSDataProvider"


class Location(geopy.Location):
    def __init__(self, *args, **kwargs):
        if args and isinstance(args[0], geopy.Location):
            self._wrapped_obj = args[0]
        else:
            super().__init__(*args, **kwargs)

    def __getattr__(self, attr):
        if attr in self.__dict__:
            return getattr(self, attr)
        if "_wrapped_obj" in dir(self) and attr in dir(self._wrapped_obj):
            return getattr(self._wrapped_obj, attr)
        raise AttributeError(f"Location object has no attribute {attr}")

    def _find_in_raw(self, field):
        if not self.raw:
            return None
        try:
            if self.service == GOOGLE_SERVICE:
                for component in self.raw["address_components"]:
                    if field in component["types"]:
                        return component["short_name"]
                return None
            if self.service == SMARTYSTREETS_SERVICE:
                return self.raw["components"].get(field)
            if self.service == SMARTYSTEETS_ZIPCODE_SERVICE:
                return self.raw.get(field)
            if self.service == NOMINATIM_SERVICE:
                return self.raw["address"].get(field)
            if self.service == LOCAL_USDATA_SERVICE:
                return self.raw.get(field)
            return self.raw.get(field)
        except KeyError:
            return self.raw.get(field)

    @property
    def service(self):
        return getattr(self, "_service", "UnknownService")

    @service.setter
    def service(self, value):
        self._service = value

    @property
    def state(self):
        if self.service == GOOGLE_SERVICE:
            return self._find_in_raw("administrative_area_level_1")
        if self.service in [SMARTYSTREETS_SERVICE, SMARTYSTEETS_ZIPCODE_SERVICE]:
            return self._find_in_raw("state_abbreviation")
        if self.service == NOMINATIM_SERVICE:
            if self._find_in_raw("country_code") == "us":
                return US_STATE_NAME_DICT.get(self._find_in_raw("state"))
            if self._find_in_raw("country_code") == "ca":
                return CA_PROVINCE_NAME_DICT.get(self._find_in_raw("state"))
        return self._find_in_raw("state")

    @property
    def latlon(self):
        return (self.latitude, self.longitude)

    @property
    def postal(self):
        if self.service == GOOGLE_SERVICE:
            return self._find_in_raw("postal_code")
        if self.service == SMARTYSTREETS_SERVICE:
            return self._find_in_raw("zipcode")
        if self.service == NOMINATIM_SERVICE:
            return self._find_in_raw("postcode")
        return self._find_in_raw("zipcode")


class LocationError(TypeError):
    pass


class Geocoder:
    def __init__(self, api_name=None, api_key=None, country="US"):
        if not (api_name or api_key):
            api_name = os.environ.get("GEOCODE_PROVIDER", "nominatim").lower()
            api_key = os.environ.get("GEOCODE_API_KEY")

        service = geopy.geocoders.get_geocoder_for_service(api_name)
        self.country = country

        if api_name == "nominatim":
            self.client = service(country_bias=country, timeout=5, user_agent="CallPower")
        elif api_name == "liveaddress":
            auth_token = os.environ.get("GEOCODE_API_TOKEN")
            self.client = service(api_key, auth_token, timeout=3)
            self.client_uszipcode = SmartystreetsUSZipcode(api_key, auth_token)
        elif api_key:
            self.client = service(api_key=api_key, timeout=3)
        else:
            raise LocationError("configure GEOCODE_PROVIDER and GEOCODE_API_KEY")

    def get_service_name(self):
        return self.client.__class__.__name__.split(".")[-1]

    def postal(self, code, country="us", provider=None):
        if provider and country == "us":
            districts = provider.get_districts(code)
            if districts:
                location = Location(code, (None, None), districts[0])
                location.service = LOCAL_USDATA_SERVICE
                return location
        return self.geocode(code, postal_only=True)

    def geocode(self, address, postal_only=False):
        service = self.get_service_name()
        if not address:
            raise LocationError("empty string passed to geocoder")

        try:
            if service == GOOGLE_SERVICE:
                response = self.client.geocode(address, region=self.country)
            elif service == NOMINATIM_SERVICE:
                response = self.client.geocode(address, addressdetails=True)
                if not response:
                    return Location()
                intermediate = Location(response)
                if postal_only or not intermediate.postal:
                    response = self.client.reverse(intermediate.latlon)
            elif service == SMARTYSTREETS_SERVICE:
                response = (
                    self.client_uszipcode.geocode(address)
                    if postal_only
                    else self.client.geocode(address, exactly_one=True)
                )
            else:
                response = self.client.geocode(address)

            result = Location(response)
            result.service = service
            if service == SMARTYSTREETS_SERVICE and postal_only:
                result.service = SMARTYSTEETS_ZIPCODE_SERVICE
        except geopy.exc.GeocoderTimedOut:
            result = Location()
            result.service = "Timeout"
        return result

    def reverse(self, latlon):
        if isinstance(latlon, tuple):
            lat, lon = latlon
        else:
            lat, lon = latlon.split(",")
        located = Location(self.client.reverse((lat, lon)))
        located.service = self.get_service_name()
        return located


class SmartystreetsUSZipcode(geopy.geocoders.LiveAddress):
    def __init__(self, auth_id, auth_token):
        super().__init__(auth_id, auth_token)
        self.api = "https://us-zipcode.api.smartystreets.com/lookup"

    def _compose_url(self, zipcode):
        query = {
            "auth-id": self.auth_id,
            "auth-token": self.auth_token,
            "zipcode": zipcode,
        }
        return f"{self.api}?{geopy.compat.urlencode(query)}"

    @staticmethod
    def _format_structured_address(matches):
        if matches.get("zipcodes"):
            best_match = matches.get("zipcodes")[0]
        else:
            return None
        latitude = best_match.get("latitude")
        longitude = best_match.get("longitude")
        return Location(
            address=best_match.get("zipcode"),
            point=(latitude, longitude) if latitude and longitude else None,
            raw=best_match,
        )
