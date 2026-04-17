from collections import defaultdict


def adapt_by_key(key):
    if key.startswith("us:bioguide"):
        return UnitedStatesData()
    if key.startswith("us_state:openstates"):
        return OpenStatesData()
    if key.startswith("us_state:governor"):
        return GovernorAdapter()
    if key.startswith("ca:opennorth"):
        return OpenNorthAdapter()
    if key.startswith("custom"):
        return CustomDataAdapter()
    return DataAdapter()


class DataAdapter:
    def key(self, key, split_by="-"):
        return key.split(split_by, 1) if split_by in key else (key, "")

    def target(self, data):
        return data

    def offices(self, data):
        return [data]


class CustomDataAdapter(DataAdapter):
    def target(self, data):
        adapted = {"title": data.get("title", ""), "uid": data.get("uid", ""), "number": data.get("number", "")}
        if "first_name" in data and "last_name" in data:
            adapted["name"] = f"{data['first_name']} {data['last_name']}"
        else:
            adapted["name"] = data.get("name", "Unknown")
        return adapted


class UnitedStatesData(DataAdapter):
    def key(self, key):
        return key.split("-", 1) if "-" in key else (key, "")

    def target(self, data):
        adapted = {
            "number": data.get("phone", ""),
            "title": data.get("title", ""),
            "uid": data.get("bioguide_id", ""),
            "location": "DC",
            "name": data.get("name") or f"{data.get('nick_name') or data.get('first_name', '')} {data.get('last_name', '')}".strip(),
            "district": f"{data.get('state', '')}-{data.get('district')}" if data.get("district") else data.get("state", ""),
        }
        return adapted

    def offices(self, data):
        offices = []
        for office in data.get("offices", []):
            if "phone" not in office:
                continue
            entry = {
                "name": office.get("city", ""),
                "number": office.get("phone", ""),
                "uid": office.get("id", ""),
                "type": "district",
                "address": " ".join(filter(None, [office.get("address"), office.get("building"), office.get("city"), office.get("state")])),
            }
            if "latitude" in office and "longitude" in office:
                entry["latlon"] = f"POINT({office['latitude']}, {office['longitude']})"
            offices.append(entry)
        return offices


class OpenStatesData(DataAdapter):
    def target(self, data):
        adapted = {"uid": data.get("id") or data.get("leg_id")}
        chamber = data.get("chamber")
        if isinstance(chamber, list):
            chamber_value = chamber[0]["organization"]["classification"]
            district = chamber[0]["post"]["label"]
        elif isinstance(chamber, str):
            chamber_value = chamber
            district = data.get("district", "")
        else:
            chamber_value = None
            district = None
        adapted["title"] = data.get("title") or ("Senator" if chamber_value == "upper" else "Representative")
        adapted["district"] = district
        adapted["name"] = data.get("name") or data.get("full_name") or f"{data.get('givenName', '')} {data.get('familyName', '')}".strip()
        if data.get("contactDetails"):
            office_phones = [detail for detail in data["contactDetails"] if detail["type"] == "voice"]
            for office in office_phones:
                if office.get("note") == "Capitol Office":
                    adapted["number"] = office.get("value", "")
            if "number" not in adapted and office_phones:
                adapted["number"] = office_phones[0].get("value", "")
        return adapted

    def offices(self, data):
        offices_dict = defaultdict(dict)
        for contact in data.get("contactDetails", []):
            offices_dict[contact["note"]][contact["type"]] = contact["value"]
            offices_dict[contact["note"]]["name"] = contact["note"]
        results = []
        for office in offices_dict.values():
            office_name = office.get("name", "").replace("Office", "").replace("office", "")
            if "#" in office_name:
                office_name = office_name.split("#")[0]
            results.append({
                "name": office_name,
                "address": office.get("address", ""),
                "number": office.get("voice", ""),
                "type": office.get("name", ""),
            })
        return results


class GovernorAdapter(DataAdapter):
    def target(self, data):
        return {
            "title": data.get("title", ""),
            "number": data.get("phone", ""),
            "uid": data.get("state", ""),
            "district": data.get("state", ""),
            "name": data.get("full_name") or f"{data.get('first_name', '')} {data.get('last_name', '')}".strip(),
        }

    def offices(self, data):
        return []


class OpenNorthAdapter(DataAdapter):
    def key(self, key, split_by=None):
        return (key, "")

    def target(self, data):
        offices = data.get("offices") or []
        legislature_office = [office for office in offices if office["type"] == "legislature"]
        return {
            "title": data.get("title") or data.get("elected_office", ""),
            "uid": data.get("cache_key", ""),
            "district": data.get("district_name", ""),
            "number": legislature_office[0].get("tel", "") if legislature_office else "",
            "name": data.get("full_name") or data.get("name", "Unknown"),
        }

    def offices(self, data):
        return [
            {
                "name": office.get("type", ""),
                "address": office.get("postal", ""),
                "number": office.get("tel", ""),
                "type": office.get("type", ""),
            }
            for office in data.get("offices", [])
            if office.get("type") != "legislature" and "tel" in office
        ]
