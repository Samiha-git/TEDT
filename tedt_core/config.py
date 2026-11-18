"""Static configuration: paths, governorates, palette, published reference aggregates."""
from __future__ import annotations

import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
GEO_PATH = DATA_DIR / "geo" / "tunisia_governorates.geojson"
CATALOG_PATH = DATA_DIR / "catalog" / "data_sources.csv"
OFFICIAL_DIR = DATA_DIR / "official"
DB_PATH = DATA_DIR / "tedt_scenarios.sqlite"

SYNTHETIC_SEED = 2026

# key = shapeName used in the GeoJSON (geoBoundaries ADM1, CC BY 4.0) ; (French, Arabic)
GOVERNORATES: dict[str, tuple[str, str]] = {
    "Tunis": ("Tunis", "تونس"),
    "Ariana": ("Ariana", "أريانة"),
    "Ben Arous": ("Ben Arous", "بن عروس"),
    "Manouba": ("Manouba", "منوبة"),
    "Nabeul": ("Nabeul", "نابل"),
    "Zaghouan": ("Zaghouan", "زغوان"),
    "Bizerte": ("Bizerte", "بنزرت"),
    "Béja": ("Béja", "باجة"),
    "Jendouba": ("Jendouba", "جندوبة"),
    "El Kef": ("Le Kef", "الكاف"),
    "Siliana": ("Siliana", "سليانة"),
    "Sousse": ("Sousse", "سوسة"),
    "Monastir": ("Monastir", "المنستير"),
    "Mahdia": ("Mahdia", "المهدية"),
    "Sfax": ("Sfax", "صفاقس"),
    "Kairouan": ("Kairouan", "القيروان"),
    "Kasserine": ("Kasserine", "القصرين"),
    "Sidi Bouzid": ("Sidi Bouzid", "سيدي بوزيد"),
    "Gabès": ("Gabès", "قابس"),
    "Médenine": ("Médenine", "مدنين"),
    "Tataouine": ("Tataouine", "تطاوين"),
    "Gafsa": ("Gafsa", "قفصة"),
    "Tozeur": ("Tozeur", "توزر"),
    "Kébili": ("Kébili", "قبلي"),
}

LEVELS = ("primary", "secondary")
LEVEL_LABELS = {
    "primary": ("الابتدائي (مع التحضيري)", "Primaire (avec préparatoire)"),
    "secondary": ("الإعدادي والثانوي", "Collège et lycée"),
}

SUBJECTS = {
    "arabic": ("العربية", "Arabe"),
    "french": ("الفرنسية", "Français"),
    "math": ("الرياضيات", "Mathématiques"),
    "science": ("العلوم", "Sciences"),
}

BLOOM_LEVELS = (
    ("remember", "التذكّر", "Mémoriser"),
    ("understand", "الفهم", "Comprendre"),
    ("apply", "التطبيق", "Appliquer"),
    ("analyze", "التحليل", "Analyser"),
    ("evaluate", "التقييم", "Évaluer"),
    ("create", "الإبداع", "Créer"),
)

# Published national aggregates for 2026-2027, as relayed by the press from the Ministry of
# Education (Tuniscope, 14 Sep 2026). Used ONLY to set the order of magnitude of the synthetic data
# and shown in the UI as "reference to verify". Not an official download.
REFERENCE_AGGREGATES = {
    "pupils_total": 2_341_000,
    "pupils_primary": 1_195_000,
    "pupils_secondary": 1_146_000,
    "teachers_total": 161_300,
    "teachers_primary": 79_025,
    "teachers_secondary": 82_318,
    "classes_total": 92_190,
    "classes_primary": 54_049,
    "classes_secondary": 38_141,
    "institutions_total": 6_178,
    "institutions_primary": 4_604,
    "institutions_secondary": 1_574,
}
REFERENCE_SOURCE = {
    "label": "Tuniscope, 14/09/2026 (d'après les données statistiques du ministère de l'Éducation)",
    "url": "https://www.tuniscope.com/article/439918/actualites/tunisie/rentre-scolaire-tunisie-320417",
    "status": "تقدير صحفي يحتاج إلى مطابقة مع المصدر الوزاري / Relais presse à confirmer auprès du ministère",
}

# TEDT visual identity: navy, steel blue, turquoise, emerald, amber and cool grey.
PALETTE = {
    "ink": "#172B4D",
    "blue": "#1B4F72",
    "blue_light": "#65C7E8",
    "sand": "#F2F4F7",
    "terracotta": "#F5A623",  # retained key for compatibility; now amber
    "olive": "#20C997",       # retained key for compatibility; now emerald
    "gold": "#F5A623",
    "red": "#C94C4C",
    "grey": "#8A9AAF",
    "navy": "#0D1B2A",
    "teal": "#0FA3A3",
    "green": "#20C997",
}
SEQUENTIAL = [[0.0, "#E7F5F8"], [0.5, "#65C7E8"], [1.0, "#0D1B2A"]]
DIVERGING = [[0.0, "#F5A623"], [0.5, "#EEF3F8"], [1.0, "#0FA3A3"]]

# --------------------------------------------------------------------------------------
# Governorate name normalisation (for imported files)
# --------------------------------------------------------------------------------------
_ALIASES = {
    "kef": "El Kef", "le kef": "El Kef", "el kef": "El Kef", "الكاف": "El Kef",
    "la manouba": "Manouba", "manouba": "Manouba", "منوبة": "Manouba",
    "kebili": "Kébili", "kébili": "Kébili", "قبلي": "Kébili",
    "gabes": "Gabès", "gabès": "Gabès", "قابس": "Gabès",
    "medenine": "Médenine", "médenine": "Médenine", "مدنين": "Médenine",
    "beja": "Béja", "béja": "Béja", "باجة": "Béja",
}


def _strip(s: str) -> str:
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode() or str(s)
    return s.strip().lower()


def normalize_governorate(name: object) -> str | None:
    """Map a free-text governorate name (FR/AR/EN spelling variants) to the canonical key."""
    if name is None:
        return None
    raw = str(name).strip()
    low = raw.lower()
    for prefix in ("gouvernorat de ", "gouvernorat d'", "governorate of ", "ولاية "):
        if low.startswith(prefix):
            raw, low = raw[len(prefix):].strip(), low[len(prefix):].strip()
    if low in _ALIASES:
        return _ALIASES[low]
    for key, (fr, ar) in GOVERNORATES.items():
        if raw == ar or raw == key or low == key.lower() or low == fr.lower():
            return key
    stripped = _strip(raw)
    if stripped in _ALIASES:
        return _ALIASES[stripped]
    for key, (fr, _ar) in GOVERNORATES.items():
        if stripped in (_strip(key), _strip(fr)):
            return key
    return None
