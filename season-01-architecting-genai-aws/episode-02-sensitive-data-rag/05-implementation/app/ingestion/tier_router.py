"""Tier routing at ingestion (CTL-010; boundary B9).

INTERNAL and CONFIDENTIAL section objects go to the shared tier; RESTRICTED objects to the restricted tier only. The
object's tier must agree with the tier its own label belongs to; anything else is never written anywhere.
"""
from core.tier_selection import tier_for_label


def route(section_object):
    tier = tier_for_label(section_object.label)
    if tier != section_object.tier:
        raise ValueError("section object tier does not match its label")
    return tier
