#%% [markdown]

# # Respa notebook

# Make sure to have DATABASE_URL pointing somewhere data is. Other settings aren't that useful here.

#%%

# Django settings require some extra
import os

os.chdir("work/respa")

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


# %%
from rich import print as rprint
from rich.console import Console

console = Console()

# %% [markdown]

## Respa tilastojen avain

"""
 - PVM
 - Tila (mielellään uniikki id, me voidaan sitten muuttaa ne käyttäjäystävällisempään muotoon raporteissa)
 - asiakkaiden varaamat tunnit edelliselle päivälle
 - henkilökunnan varaamat tunnit edelliselle päivälle
 - varattava olleet tunnit (/aukiolo)
 - asiakkaiden tekemät varaukset edelliselle päivälle (kpl)
 - henkilökunnan tekemät varaukset edelliselle päivälle (kpl)
 - ? dumpin ottohetkestä eteenpäin olevien asiakasvarausten tuntimäärä (varauspaine)
 - ? dumpin ottohetkestä eteenpäin olevien henkilökuntavarausten tuntimäärä (varauspaine)
 - varattavissa oleva tuntimäärä dumpin ottohetkestä eteenpäin
 - asiakkaiden varausmäärä tulevaisuudessa
 - henkilökunnan varausmäärä tulevaisuudessa
 - Tuntimäärät ja varausmäärät ovat kaikki ajohetkeltä.
"""

# %%

import datetime
import pytz
import dateutil.tz
import dateutil.relativedelta

today_start = datetime.datetime.now(dateutil.tz.tzlocal()).replace(
    hour=0, minute=0, second=0, microsecond=0
)
today_end = datetime.datetime.now(dateutil.tz.tzlocal()).replace(
    hour=0, minute=0, second=0, microsecond=0
) + dateutil.relativedelta.relativedelta(days=1)

# TODO: month to days=-1
dt_start = today_start.replace(month=1, year=2019)
dt_end = today_end.replace(month=1, year=2019)

future = today_end.replace(year=today_end.year + 2)

# %%


def asiakasvaraukset_lkm(tila, dt_start, dt_end):
    return Reservation.objects.filter(
        resource__unit=tila, staff_event=False, begin__gt=dt_start, end__lt=dt_end
    ).count()


def hkvaraukset_lkm(tila, dt_start, dt_end):
    return Reservation.objects.filter(
        resource__unit=tila, staff_event=True, begin__gt=dt_start, end__lt=dt_end
    ).count()


from django.db.models import Sum
from django.db.models import F


def asiakasvaraukset_tunneittain(tila, dt_start, dt_end):
    return (
        Reservation.objects.filter(
            resource__unit=tila, staff_event=False, begin__gt=dt_start, end__lt=dt_end
        )
        .aggregate(total=Sum(F("end") - F("begin")))["total"]
        .total_seconds()
        / 60
        / 60
    )


def hkvaraukset_tunneittain(tila, dt_start, dt_end):
    try:
        return (
            Reservation.objects.filter(
                resource__unit=tila,
                staff_event=True,
                begin__gt=dt_start,
                end__lt=dt_end,
            )
            .aggregate(total=Sum(F("end") - F("begin")))["total"]
            .total_seconds()
            / 60
            / 60
        )
    except AttributeError:
        return 0

#%%


def varattavat_tunnit(tila, dt_start, dt_end):
    # TODO: do this
    return 0


# %%
oodi = Unit.objects.get(pk="tprek:51342")

res = [
    [
        oodi,
        asiakasvaraukset_tunneittain(oodi, dt_start, dt_end),
        hkvaraukset_tunneittain(oodi, dt_start, dt_end),
        asiakasvaraukset_lkm(oodi, dt_start, dt_end),
        hkvaraukset_lkm(oodi, dt_start, dt_end),
        varattavat_tunnit(oodi, dt_start, dt_end),
        asiakasvaraukset_tunneittain(oodi, dt_start, future),
        hkvaraukset_tunneittain(oodi, dt_start, future),
        varattavat_tunnit(oodi, dt_start, future),
        asiakasvaraukset_lkm(oodi, dt_start, future),
        hkvaraukset_lkm(oodi, dt_start, future),
    ]
]

# %%
import pandas

df = pandas.DataFrame(
    res,
    columns=[
        "Tila",
        "Asiakasvaraukset tunnit",
        "Henkilökuntavaraukset tunnit",
        "Asiakasvaraukset lkm",
        "Henkilökuntavaraukset lkm",
        "Varattavat tunnit",
        "Asiakasvaraukset tuleva tuntimäärä",
        "Henkilökuntavaraukset tuleva tuntimäärä",
        "Varattavat tunnit tulevaisuudessa",
        "Asiakasvaraukset tulevaisuudessa",
        "Henkilökuntavaraukset tulevaisuudessa",
    ],
)
df.style.set_caption(f"Respa tilastot {today_start}")

# %%
