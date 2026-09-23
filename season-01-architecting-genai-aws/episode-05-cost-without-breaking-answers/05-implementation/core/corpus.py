#!/usr/bin/env python3
"""PUBLISHABLE CORE — synthetic corpus.

Kestrelmoor Rail Systems is FICTIONAL. Every document, section and person here is SYNTHETIC and was
written for teaching. Nothing in this file is, or may be presented as, real operational content or
observed production traffic.

This is the learner-safe core. It deliberately contains ONLY what the public lab needs. It has no
model provider, no cloud SDK, no evaluation machinery, and no test-only negative control.
"""
from dataclasses import dataclass, field

INTERNAL, CONFIDENTIAL = "INTERNAL", "CONFIDENTIAL"


@dataclass
class Section:
    section_id: str
    doc_id: str
    label: str
    domain: str | None
    text: str
    steps: list[str] = field(default_factory=list)


@dataclass
class Document:
    doc_id: str
    title: str
    state: str = "IN_FORCE"          # IN_FORCE | WITHDRAWN
    version: int = 1


@dataclass
class Principal:
    principal_id: str
    active: bool = True
    domains: set = field(default_factory=set)


DOCUMENTS = {d.doc_id: d for d in [
    Document("D-100", "Points machine isolation procedure"),
    Document("D-101", "Depot induction - PPE requirements"),
    Document("D-102", "Shift handover checklist"),
    Document("D-200", "Orion bid pricing schedule"),      # CONFIDENTIAL - never reusable
]}

SECTIONS = {s.section_id: s for s in [
    Section('D-100#1', 'D-100', INTERNAL, None,
            'Isolation of a points machine must begin with confirming the machine reference against the work order. Do not proceed if the reference does not match.',
            ['confirm machine reference against the work order', 'do not proceed if the reference does not match']),
    Section('D-100#2', 'D-100', INTERNAL, None,
            'Apply the mechanical lock before removing electrical supply. Fit the danger tag with your name and the time. Only then isolate the supply at the local cabinet.',
            ['apply the mechanical lock before removing electrical supply', 'fit the danger tag with name and time', 'isolate the supply at the local cabinet']),
    Section('D-100#3', 'D-100', INTERNAL, None,
            'Prove dead at the terminals before any work. Never energise while a danger tag is fitted.',
            ['prove dead at the terminals before any work', 'never energise while a danger tag is fitted']),
    Section('D-101#1', 'D-101', INTERNAL, None,
            'All depot visitors wear high-visibility clothing and safety footwear. Eye protection is required in the grinding bay.',
            ['wear high-visibility clothing and safety footwear', 'eye protection required in the grinding bay']),
    Section('D-102#1', 'D-102', INTERNAL, None,
            'At handover, record outstanding defects, isolations still in force and any tags not yet removed. An isolation may not be handed over verbally.',
            ['record outstanding defects', 'record isolations still in force', 'record tags not yet removed', 'an isolation may not be handed over verbally']),
    Section("D-200#1", "D-200", CONFIDENTIAL, "BID-ORION",
            "Indicative pricing for the Orion framework bid.",
            ["do not disclose indicative pricing outside the bid team"]),
]}

PRINCIPALS = {p.principal_id: p for p in [
    Principal("P-01"),                             # ordinary active employee
    Principal("P-02"),                             # ordinary active employee
    Principal("P-03", domains={"BID-ORION"}),      # bid-domain member
]}


def eligible(principal, section):
    """Episode 02's rule: decided PER SECTION, from CURRENT grants, on every request."""
    if not principal.active:
        return False
    if section.label == INTERNAL:
        return True
    return section.domain in principal.domains


def in_force(section):
    """Episode 03's rule: a section is servable only while its document is IN_FORCE."""
    return DOCUMENTS[section.doc_id].state == "IN_FORCE"
