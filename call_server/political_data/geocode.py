from geocodio import GeocodioClient
import os

# light wrapper around geocode.io client
# with convenience properties to hide address components
# TODO, add non-US postal endpoints


class Location(dict):
    @property
    def state(self):
        if 'state' in self:
            return self.get('state')
        elif 'address_components' in self.keys():
            return self.get('address_components', {}).get('state')
        else:
            return None

    @property
    def latlon(self):
        lat = self.get('location', {}).get('lat')
        lon = self.get('location', {}).get('lng')
        return (lat, lon)

    @property
    def zipcode(self):
        if 'zipcode' in self:
            return self.get('zipcode')
        elif 'address_components' in self.keys():
            return self.get('address_components', {}).get('zipcode')
        else:
            return None



class Geocoder(object):
    def __init__(self, API_KEY=None):
        if not API_KEY:
            # get keys from os.environ, because we may not have current_app context
            API_KEY = os.environ.get('GEOCODE_API_KEY')
        self.client = GeocodioClient(API_KEY)

    def zipcode(self, zipcode, cache=None):
        if cache:
            districts = cache.get_district(zipcode)
            if len(districts) == 1:
                d = districts[0]
                d['source'] = 'local district cache'
                return Location(d)
            else:
                # TODO, how to handle districts that span states?
                return self.geocode(zipcode)
        else:
            return self.geocode(zipcode)

    def geocode(self, address):
        results = self.client.geocode(address).get('results')
        if not results:
            return None
        else:
            return Location(results[0])

    def reverse(self, latlon):
        if type(latlon) == tuple:
            lat = latlon[0]
            lon = latlon[1]
        else:
            try:
                (lat, lon) = latlon.split(',')
            except ValueError:
                raise ValueError('unable to parse latlon as either tuple or comma delimited string')

        results = self.client.reverse((lat, lon)).get('results')
        if not results:
            return None
        else:
            return Location(results[0])
