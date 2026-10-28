"""
Geography helpers: detect country from a location string, expand US states,
and produce friendly country labels. Used by connectors (for filtering) and
the workbook (for display).
"""
import re

US_STATES = {
    "AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas",
    "CA": "California", "CO": "Colorado", "CT": "Connecticut", "DE": "Delaware",
    "FL": "Florida", "GA": "Georgia", "HI": "Hawaii", "ID": "Idaho",
    "IL": "Illinois", "IN": "Indiana", "IA": "Iowa", "KS": "Kansas",
    "KY": "Kentucky", "LA": "Louisiana", "ME": "Maine", "MD": "Maryland",
    "MA": "Massachusetts", "MI": "Michigan", "MN": "Minnesota", "MS": "Mississippi",
    "MO": "Missouri", "MT": "Montana", "NE": "Nebraska", "NV": "Nevada",
    "NH": "New Hampshire", "NJ": "New Jersey", "NM": "New Mexico", "NY": "New York",
    "NC": "North Carolina", "ND": "North Dakota", "OH": "Ohio", "OK": "Oklahoma",
    "OR": "Oregon", "PA": "Pennsylvania", "RI": "Rhode Island", "SC": "South Carolina",
    "SD": "South Dakota", "TN": "Tennessee", "TX": "Texas", "UT": "Utah",
    "VT": "Vermont", "VA": "Virginia", "WA": "Washington", "WV": "West Virginia",
    "WI": "Wisconsin", "WY": "Wyoming", "DC": "District of Columbia",
}
_STATE_NAMES = {v.lower(): k for k, v in US_STATES.items()}

# Checked in order; first match wins. Non-target countries are here so they get
# detected and filtered out instead of defaulting to US.
_COUNTRY_KEYWORDS = [
    ("ca", ["canada", "toronto", "montreal", "montréal", "vancouver", "ontario",
            "quebec", "québec", "ottawa", "calgary", "edmonton", "winnipeg"]),
    ("mx", ["mexico", "méxico", "cdmx", "guadalajara", "monterrey", "mexico city"]),
    ("gb", ["united kingdom", "london", "manchester", "england", "scotland",
            "edinburgh", "birmingham", "glasgow", "leeds", "bristol"]),
    ("br", ["brazil", "brasil", "são paulo", "sao paulo", "rio de janeiro"]),
    ("es", ["spain", "españa", "madrid", "barcelona", "valencia"]),
    ("de", ["germany", "berlin", "munich", "münchen", "frankfurt", "hamburg"]),
    ("fr", ["france", "paris", "lyon"]),
    ("in", ["india", "bangalore", "bengaluru", "mumbai", "hyderabad", "gurgaon",
            "gurugram", "pune", "delhi", "noida", "chennai"]),
    ("sg", ["singapore"]),
    ("au", ["australia", "sydney", "melbourne", "brisbane"]),
    ("ie", ["ireland", "dublin"]),
    ("nl", ["netherlands", "amsterdam"]),
    ("hk", ["hong kong"]),
    ("jp", ["japan", "tokyo"]),
    ("ae", ["dubai", "abu dhabi", "united arab emirates"]),
    ("ph", ["philippines", "manila"]),
    ("pl", ["poland", "warsaw", "kraków", "krakow"]),
]

_LABELS = {"us": "US", "ca": "Canada", "mx": "Mexico", "gb": "UK"}


def country_from_loc(loc):
    """Return a 2-letter country code, or '' if unknown. US detection uses
    explicit markers, a ', ST' state abbreviation, or a spelled-out state name."""
    if not loc:
        return ""
    l = loc.lower()
    for code, kws in _COUNTRY_KEYWORDS:
        for kw in kws:
            if kw in l:
                return code
    if any(k in l for k in ["united states", " usa", ",usa", " u.s", "remote - us",
                            "remote, us", "remote (us", "u.s.a"]):
        return "us"
    m = re.search(r",\s*([A-Za-z]{2})\b", loc)
    if m and m.group(1).upper() in US_STATES:
        return "us"
    for name in _STATE_NAMES:
        if re.search(r"\b" + re.escape(name) + r"\b", l):
            return "us"
    return ""


def us_state(loc):
    """Full US state name from a location string, or '' if none found."""
    if not loc:
        return ""
    m = re.search(r",\s*([A-Za-z]{2})\b", loc)
    if m and m.group(1).upper() in US_STATES:
        return US_STATES[m.group(1).upper()]
    l = loc.lower()
    for name, ab in _STATE_NAMES.items():
        if re.search(r"\b" + re.escape(name) + r"\b", l):
            return US_STATES[ab]
    if "remote" in l:
        return "Remote"
    return ""


def label(code):
    if not code:
        return ""
    return _LABELS.get(code, code.upper())
