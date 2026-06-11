"""Survey form field visibility configuration."""

from __future__ import annotations

import json
from copy import deepcopy

DEFAULT_FORM_CONFIG: dict = {
    "surveyorFields": {
        "assembly": True,
        "ward": True,
        "pollingStation": True,
        "surveyorName": True,
        "surveyorMobile": True,
    },
    "voterFields": {
        "interviewerName": True,
        "interviewerAge": True,
        "interviewerGender": True,
        "interviewerCaste": True,
        "interviewerCommunity": True,
        "interviewerMobile": True,
        "interviewerEducation": True,
        "interviewerWork": True,
        "interviewerHouseholdIncome": True,
        "interviewerCurrentAddress": True,
        "voterOfConstituency": True,
    },
    "enableVoterSearch": True,
    "manualEntryWhenApiEmpty": True,
}


def normalize_form_config(raw: dict | None) -> dict:
    base = deepcopy(DEFAULT_FORM_CONFIG)
    if not raw:
        return base
    if isinstance(raw.get("surveyorFields"), dict):
        base["surveyorFields"].update({k: bool(v) for k, v in raw["surveyorFields"].items()})
    if isinstance(raw.get("voterFields"), dict):
        base["voterFields"].update({k: bool(v) for k, v in raw["voterFields"].items()})
    if "enableVoterSearch" in raw:
        base["enableVoterSearch"] = bool(raw["enableVoterSearch"])
    if "manualEntryWhenApiEmpty" in raw:
        base["manualEntryWhenApiEmpty"] = bool(raw["manualEntryWhenApiEmpty"])
    return base


def parse_form_config_json(value: str | None) -> dict:
    if not value:
        return deepcopy(DEFAULT_FORM_CONFIG)
    try:
        return normalize_form_config(json.loads(value))
    except json.JSONDecodeError:
        return deepcopy(DEFAULT_FORM_CONFIG)


def dump_form_config_json(config: dict) -> str:
    return json.dumps(normalize_form_config(config), separators=(",", ":"))
