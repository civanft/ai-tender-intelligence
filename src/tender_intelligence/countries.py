"""EU-27 buyer-market catalogue, shared by ingestion, analysis and the UI.

Membership source: https://european-union.europa.eu/principles-countries-history/eu-countries_en
TED uses ISO 3166-1 alpha-3 buyer-country values (GRC, not EL).
"""

EU_COUNTRY_NAMES = {
    "AUT": "Austria", "BEL": "Belgium", "BGR": "Bulgaria",
    "HRV": "Croatia", "CYP": "Cyprus", "CZE": "Czechia",
    "DNK": "Denmark", "EST": "Estonia", "FIN": "Finland",
    "FRA": "France", "DEU": "Germany", "GRC": "Greece",
    "HUN": "Hungary", "IRL": "Ireland", "ITA": "Italy",
    "LVA": "Latvia", "LTU": "Lithuania", "LUX": "Luxembourg",
    "MLT": "Malta", "NLD": "Netherlands", "POL": "Poland",
    "PRT": "Portugal", "ROU": "Romania", "SVK": "Slovakia",
    "SVN": "Slovenia", "ESP": "Spain", "SWE": "Sweden",
}
EU_COUNTRY_CODES = tuple(EU_COUNTRY_NAMES)

# Labels always accompany color; colors repeat deliberately for EU-wide charts.
_COLORS = ("#315EAA", "#34796F", "#A75048", "#70609A", "#9B763F", "#457E92", "#747B46")
EU_COUNTRY_COLORS = {code: _COLORS[i % len(_COLORS)] for i, code in enumerate(EU_COUNTRY_CODES)}
EU_COUNTRY_COLORS.update({"BEL": "#315EAA", "ITA": "#A75048", "FIN": "#34796F"})
