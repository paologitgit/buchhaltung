"""Kategorien von Auftrittsorten.

Jede Kategorie kennt ihre OSM-Tag-Selektoren (für die Overpass API) und
Google-Textsuchen (für die Places API). Kategorien ohne OSM-Selektoren
(z.B. Hochzeitsplaner) liefern nur mit Google-API-Key Resultate.
"""

CATEGORIES = [
    # key, label, gruppe, osm-selektoren, google-suchbegriffe, standardmässig aktiv
    {
        "key": "bar_pub", "label": "Bars & Pubs", "group": "Gastronomie",
        "osm": ['["amenity"="bar"]', '["amenity"="pub"]'],
        "google": ["Bar", "Pub"], "default": True,
    },
    {
        "key": "cafe", "label": "Cafés", "group": "Gastronomie",
        "osm": ['["amenity"="cafe"]'],
        "google": ["Café"], "default": True,
    },
    {
        "key": "restaurant", "label": "Restaurants", "group": "Gastronomie",
        "osm": ['["amenity"="restaurant"]'],
        "google": ["Restaurant"], "default": False,
    },
    {
        "key": "weinbar", "label": "Weinbars & Vinotheken", "group": "Wein & Genuss",
        "osm": ['["shop"="wine"]'],
        "google": ["Weinbar", "Vinothek"], "default": True,
    },
    {
        "key": "weingut", "label": "Weingüter", "group": "Wein & Genuss",
        "osm": ['["craft"="winery"]'],
        "google": ["Weingut"], "default": True,
    },
    {
        "key": "brauerei", "label": "Brauereien & Braupubs", "group": "Wein & Genuss",
        "osm": ['["craft"="brewery"]', '["microbrewery"="yes"]'],
        "google": ["Brauerei"], "default": False,
    },
    {
        "key": "eventlocation", "label": "Eventlocations", "group": "Events",
        "osm": ['["amenity"="events_venue"]', '["amenity"="conference_centre"]'],
        "google": ["Eventlocation", "Festsaal"], "default": True,
    },
    {
        "key": "hochzeit", "label": "Hochzeitsplaner & Eventagenturen", "group": "Events",
        "osm": [],  # in OSM praktisch nicht erfasst
        "google": ["Hochzeitsplaner", "Eventagentur"], "default": False,
    },
    {
        "key": "hotel", "label": "Hotels", "group": "Hotellerie",
        "osm": ['["tourism"="hotel"]'],
        "google": ["Hotel"], "default": False,
    },
    {
        "key": "kultur", "label": "Kleinkunst & Kulturzentren", "group": "Kultur",
        "osm": ['["amenity"="arts_centre"]', '["amenity"="theatre"]'],
        "google": ["Kleinkunstbühne", "Kulturzentrum"], "default": True,
    },
    {
        "key": "museum", "label": "Museen & Galerien", "group": "Kultur",
        "osm": ['["tourism"="museum"]', '["tourism"="gallery"]'],
        "google": ["Museum"], "default": False,
    },
    {
        "key": "altersheim", "label": "Alters- & Pflegeheime", "group": "Weitere",
        "osm": ['["amenity"="nursing_home"]', '["social_facility"="nursing_home"]',
                '["social_facility"="assisted_living"]'],
        "google": ["Altersheim", "Pflegeheim"], "default": False,
    },
    {
        "key": "gemeinde", "label": "Gemeindeverwaltungen", "group": "Weitere",
        "osm": ['["amenity"="townhall"]'],
        "google": ["Gemeindeverwaltung"], "default": False,
    },
    {
        "key": "golf", "label": "Golfclubs", "group": "Weitere",
        "osm": ['["leisure"="golf_course"]'],
        "google": ["Golfclub"], "default": False,
    },
    {
        "key": "camping", "label": "Campingplätze", "group": "Weitere",
        "osm": ['["tourism"="camp_site"]'],
        "google": ["Campingplatz"], "default": False,
    },
]

BY_KEY = {c["key"]: c for c in CATEGORIES}


def grouped():
    """Kategorien nach Gruppe geordnet, für die Anzeige im Formular."""
    groups: dict[str, list] = {}
    for c in CATEGORIES:
        groups.setdefault(c["group"], []).append(c)
    return groups
