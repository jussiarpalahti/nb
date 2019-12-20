#%% [markdown]

# # Respa notebook

# Make sure to have DATABASE_URL pointing somewhere data is. Other settings aren't that useful here.

#%%

# Django settings require some extra
import os

if not os.environ.get("DJANGO_SETTINGS_MODULE"):
    os.environ["DJANGO_SETTINGS_MODULE"] = "respa.settings"
if not os.environ.get("DATABASE_URL"):
    os.environ["DATABASE_URL"] = "postgis:///respalab"

from django.conf import settings

# settings.configure()
import django

django.setup()

#%%

# Shell Plus Model Imports
from allauth.account.models import EmailAddress, EmailConfirmation
from allauth.socialaccount.models import SocialAccount, SocialApp, SocialToken
from caterings.models import (
    CateringOrder,
    CateringOrderLine,
    CateringProduct,
    CateringProductCategory,
    CateringProvider,
)
from comments.models import Comment
from django.contrib.admin.models import LogEntry
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType

from django.contrib.sessions.models import Session
from django.contrib.sites.models import Site
from easy_thumbnails.models import Source, Thumbnail, ThumbnailDimensions
from guardian.models import GroupObjectPermission, UserObjectPermission
from helusers.models import ADGroup, ADGroupMapping
from kulkunen.models import (
    AccessControlGrant,
    AccessControlResource,
    AccessControlSystem,
    AccessControlUser,
)
from munigeo.models import (
    Address,
    AdministrativeDivision,
    AdministrativeDivisionGeometry,
    AdministrativeDivisionTranslation,
    AdministrativeDivisionType,
    Building,
    Municipality,
    MunicipalityTranslation,
    POI,
    POICategory,
    Plan,
    Street,
    StreetTranslation,
)
from notifications.models import NotificationTemplate, NotificationTemplateTranslation
from payments.models import Order, OrderLine, OrderLogEntry, Product
from resources.models.accessibility import (
    AccessibilityValue,
    AccessibilityViewpoint,
    ResourceAccessibility,
    UnitAccessibility,
)
from resources.models.availability import Day, Period
from resources.models.equipment import Equipment, EquipmentAlias, EquipmentCategory
from resources.models.reservation import (
    Reservation,
    ReservationMetadataField,
    ReservationMetadataSet,
)
from resources.models.resource import (
    Purpose,
    Resource,
    ResourceDailyOpeningHours,
    ResourceEquipment,
    ResourceGroup,
    ResourceImage,
    ResourceType,
    TermsOfUse,
)
from resources.models.unit import Unit, UnitAuthorization, UnitIdentifier
from resources.models.unit_group import UnitGroup, UnitGroupAuthorization
from respa_exchange.models import (
    ExchangeConfiguration,
    ExchangeReservation,
    ExchangeResource,
    ExchangeUser,
    ExchangeUserX500Address,
)
from rest_framework.authtoken.models import Token
from reversion.models import Revision, Version
from users.models import User

# Shell Plus Django Imports
from django.core.cache import cache
from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import (
    Avg,
    Case,
    Count,
    F,
    Max,
    Min,
    Prefetch,
    Q,
    Sum,
    When,
    Exists,
    OuterRef,
    Subquery,
)
from django.utils import timezone
from django.urls import reverse

from psycopg2.extras import DateTimeTZRange
import datetime

#%% [markdown]

# code starts from here on

# %%

def get_use_ratio(unit, range = [datetime.date(2019, 11, 1), datetime.date(2019, 11, 30)]):
    nov = unit.periods.filter(start__range=range, end__range=range)

    # get one day's open seconds and hours

    first = nov[0]
    mon = first.days.all()[0]
    open_as_sec = mon.opens.strftime("%s")
    closed_as_sec = mon.closes.strftime("%s")
    day_length_as_sec = int(closed_as_sec) - int(open_as_sec)
    day_length_as_hours = day_length_as_sec / 60 / 60

    # This should be all reservation objects combined for Oodi on given time range

    oodi_res_length = sum(
        [
            (one_res.end - one_res.begin).total_seconds()
            for one_res in Reservation.objects.filter(
                resource__unit=unit, begin__range=range, end__range=range
            )
        ]
    )

    dt_range = DateTimeTZRange(*range)
    openings = ResourceDailyOpeningHours.objects.filter(
        resource__unit=unit, open_between__contained_by=dt_range
    )
    one_opening = openings[0]

    avail_seconds = (
        one_opening.open_between.upper - one_opening.open_between.lower
    ).total_seconds()
    avail_hours = avail_seconds / 60 / 60

    # And this should be all given time range's open times' sum in second

    all_avail_time = sum(
        [
            (
                one_opening.open_between.upper - one_opening.open_between.lower
            ).total_seconds()
            for one_opening in openings
        ]
    )

    total_use = (oodi_res_length / all_avail_time) * 100

    return total_use

# %%

oodi = Unit.objects.get(pk="tprek:51342")

ratio = get_use_ratio(oodi)
