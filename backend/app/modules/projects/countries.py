"""Valid country list for project creation."""

COUNTRIES = [
    "Afghanistan", "Albania", "Algeria", "Andorra", "Angola",
    "Argentina", "Armenia", "Australia", "Austria", "Azerbaijan",
    "Bahrain", "Bangladesh", "Belarus", "Belgium", "Bolivia",
    "Bosnia and Herzegovina", "Brazil", "Brunei", "Bulgaria",
    "Cambodia", "Cameroon", "Canada", "Chad", "Chile", "China",
    "Colombia", "Costa Rica", "Croatia", "Cuba", "Cyprus",
    "Czech Republic", "Denmark", "Dominican Republic",
    "Ecuador", "Egypt", "El Salvador", "Estonia", "Ethiopia",
    "Finland", "France",
    "Georgia", "Germany", "Ghana", "Greece", "Guatemala",
    "Honduras", "Hungary",
    "Iceland", "India", "Indonesia", "Iran", "Iraq", "Ireland",
    "Israel", "Italy",
    "Jamaica", "Japan", "Jordan",
    "Kazakhstan", "Kenya", "KSA", "Kuwait", "Kyrgyzstan",
    "Laos", "Latvia", "Lebanon", "Libya", "Lithuania", "Luxembourg",
    "Madagascar", "Malaysia", "Mali", "Malta", "Mexico", "Moldova",
    "Mongolia", "Montenegro", "Morocco", "Mozambique", "Myanmar",
    "Nepal", "Netherlands", "New Zealand", "Nigeria", "North Macedonia",
    "Norway",
    "Oman",
    "Pakistan", "Palestine", "Panama", "Paraguay", "Peru",
    "Philippines", "Poland", "Portugal",
    "Qatar",
    "Romania", "Russia", "Rwanda",
    "Saudi Arabia", "Senegal", "Serbia", "Singapore", "Slovakia",
    "Slovenia", "Somalia", "South Africa", "South Korea", "Spain",
    "Sri Lanka", "Sudan", "Sweden", "Switzerland", "Syria",
    "Taiwan", "Tajikistan", "Tanzania", "Thailand", "Tunisia",
    "Turkey", "Turkmenistan",
    "UAE", "Uganda", "Ukraine", "United Kingdom", "United States",
    "Uruguay", "Uzbekistan",
    "Venezuela", "Vietnam",
    "Yemen",
    "Zambia", "Zimbabwe",
]

COUNTRIES_SET = {c.lower() for c in COUNTRIES}
COUNTRIES_MAP = {c.lower(): c for c in COUNTRIES}


def is_valid_country(country: str) -> bool:
    return country.lower() in COUNTRIES_SET


def normalize_country(country: str) -> str:
    return COUNTRIES_MAP.get(country.lower(), country)


def normalize_city(city: str) -> str:
    """First letter capital, remaining lowercase for each word."""
    return city.strip().title()
