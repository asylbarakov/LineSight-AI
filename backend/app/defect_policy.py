"""KPI equipment defects are narrower than ML's broad defect/hazard score.

Use persisted class identifiers, not translated UI labels or priority. Unknown
equipment vocabulary stays excluded until the model's taxonomy is reviewed.
"""
from ml.classes import DATASET_CLASSES, DEFECT_KEYWORDS, RU_EQUIPMENT, normalize

HAZARD_CLASSES = frozenset({"nw", "yw"})
HAZARD_KEYWORDS = frozenset({"nest", "foreign", "vegetation", "contact"})
EQUIPMENT_TERMS = (frozenset(RU_EQUIPMENT) - {"low_visibility"}) | {"conductor", "hardware", "terminal", "lead"}
DAMAGE_KEYWORDS = tuple(k for k in DEFECT_KEYWORDS if k not in HAZARD_KEYWORDS)


def is_equipment_defect(name: str) -> bool:
    normalized = normalize(name)
    if normalized in DATASET_CLASSES:
        return normalized not in HAZARD_CLASSES
    # Recognized equipment + damage evidence, e.g. the existing synthetic
    # insulator_crack class. Hazard-only/unknown labels are not equipment faults.
    return bool(set(normalized.split("_")) & EQUIPMENT_TERMS) and any(k in normalized for k in DAMAGE_KEYWORDS)
