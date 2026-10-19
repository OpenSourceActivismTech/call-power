from django.db import transaction

from callpower.apps.core.models import Target, TargetOffice
from callpower.apps.political_data.data_cache import check_political_data_cache


@transaction.atomic
def ensure_target_from_key(key):
    existing = Target.objects.filter(key=key).order_by("-id").first()
    data = check_political_data_cache(key)
    offices = data.pop("offices", [])
    data.pop("uid", None)

    if not existing:
        target = Target.objects.create(key=key, **data)
    else:
        target = existing
        for field, value in data.items():
            setattr(target, field, value)
        target.save()

    existing_uids = {office.uid for office in target.offices.all()}
    for office_data in offices:
        office_uid = office_data.get("uid")
        if office_uid in existing_uids:
            office = target.offices.filter(uid=office_uid).first()
            for field, value in office_data.items():
                setattr(office, field, value)
            office.save()
        else:
            TargetOffice.objects.create(target=target, **office_data)
    return target
