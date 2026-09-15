"""Data tests TST-DATA-001 … TST-DATA-006 (classification authority, quarantine, special-category, provenance, tiers, cache)."""
from harness.suites import test
from core.eligibility import RESTRICTIVENESS

SPECIAL = "CANARY-SPECIAL-SI0417-MED"


def _inventory(ctx):
    ctx.marks["inventory"] = ctx.obs.inventory()
    ctx.run.attach("inventory.json", ctx.marks["inventory"])
    return ctx.marks["inventory"]


def _chunks(inventory):
    return [dict(c, tier=tier) for tier, content in inventory.items() for c in content["chunks"]]


def _latest_report(ctx, document_id):
    reports = [r for r in ctx.obs.ingestion_reports() if document_id in r.get("documents", [])]
    return reports[-1] if reports else None


def _absent_everywhere(inventory, document_id, canary):
    chunks = _chunks(inventory)
    return (not any(c["document_id"] == document_id or canary in c["canaries"] for c in chunks)
            and not any(k.startswith(f"sections/{document_id}/") for content in inventory.values()
                        for k in content["section_objects"]))


@test("TST-DATA-001", "data", ["DATA-005", "SEC-007"], ["CTL-007"], "L3",
      "Unlabelled D-09 is quarantined and reported; its canary is in neither tier")
def data_001(ctx):
    inventory = _inventory(ctx)
    report = _latest_report(ctx, "D-09") or {}
    reasons = [q["reason"] for q in report.get("quarantine", []) if q["document_id"] == "D-09"]
    absent = _absent_everywhere(inventory, "D-09", "CANARY-UNLABELLED-TOOLS")
    o = ctx.ask("P-01", "tooling")
    ctx.marks["TST-DATA-001"] = o.request_id
    passed = reasons == ["LABEL_MISSING"] and absent and not any(k.startswith("D-09") for k in o.retrieved_keys) \
        and not ctx.leaks(o)
    return passed, f"quarantine {reasons}; absent from both tiers: {absent}; P-01 retrieved {o.retrieved_keys}", \
        {"quarantine_entries": reasons, "ask": o.view()}


@test("TST-DATA-002", "data", ["DATA-001", "DATA-005", "SEC-007"], ["CTL-007"], "L3",
      "Misspelt (D-10), scope-less (D-11) and lower-case (D-15) labels are quarantined; canaries in neither tier")
def data_002(ctx):
    inventory = ctx.marks.get("inventory") or _inventory(ctx)
    expected = {"D-10": ("LABEL_INVALID", "CANARY-MALFORMED-SUPPLIER"), "D-11": ("SCOPE_MISSING", "CANARY-MALFORMED-NOSCOPE"),
                "D-15": ("LABEL_INVALID", "CANARY-MALFORMED-LOWERCASE")}
    findings = {}
    for document_id, (reason, canary) in expected.items():
        report = _latest_report(ctx, document_id) or {}
        reasons = [q["reason"] for q in report.get("quarantine", []) if q["document_id"] == document_id]
        findings[document_id] = {"reasons": reasons, "absent": _absent_everywhere(inventory, document_id, canary),
                                 "ok": reasons == [reason] and _absent_everywhere(inventory, document_id, canary)}
    asks = [ctx.ask("P-02", "supplier"), ctx.ask("P-01", "access"), ctx.ask("P-01", "parking")]
    retrieved = sorted({k for o in asks for k in o.retrieved_keys if k[:4] in ("D-10", "D-11", "D-15")})
    passed = all(f["ok"] for f in findings.values()) and not retrieved and not any(ctx.leaks(o) for o in asks)
    return passed, f"{findings}; quarantined sections retrieved: {retrieved}", \
        {"findings": findings, "asks": [o.view() for o in asks]}


@test("TST-DATA-003", "data", ["DATA-002"], ["CTL-006"], "L3",
      "D-14's text claims INTERNAL; it is indexed as CONFIDENTIAL BID-ORION; P-01 never retrieves it, P-02 does")
def data_003(ctx):
    inventory = ctx.marks.get("inventory") or _inventory(ctx)
    d14 = [(c["label"], c["scope"], c["tier"]) for c in _chunks(inventory) if c["document_id"] == "D-14"]
    p01, p02 = ctx.ask("P-01", "orion_discount"), ctx.ask("P-02", "orion_discount")
    indexed_by_record = bool(d14) and all(x == ("CONFIDENTIAL", "BID-ORION", "shared") for x in d14)
    passed = indexed_by_record and "D-14-S1" not in p01.retrieved_keys and "D-14-S1" in p02.retrieved_keys
    return passed, f"D-14 chunks {d14}; P-01 retrieved D-14: {'D-14-S1' in p01.retrieved_keys}; " \
        f"P-02 retrieved D-14: {'D-14-S1' in p02.retrieved_keys}", {"d14_chunks": d14, "asks": [p01.view(), p02.view()]}


@test("TST-DATA-004", "data", ["DATA-004", "CMP-001"], ["CTL-009"], "L3",
      "Special-category D-04 §3 is absent from both tiers' storage and vectors, retrieval, answers, audit and logs")
def data_004(ctx):
    inventory = ctx.marks.get("inventory") or _inventory(ctx)
    report = _latest_report(ctx, "D-04") or {}
    in_tiers = [c for c in _chunks(inventory) if SPECIAL in c["canaries"] or (c["document_id"], c["section_id"]) == ("D-04", "S3")]
    objects = [k for content in inventory.values() for k in content["section_objects"] if k == "sections/D-04/S3.txt"]
    asks = [ctx.ask(p, "si0417_medical") for p in ("P-01", "P-02", "P-03", "P-04", "P-05", "P-06", "P-07", "P-08", "P-10")]
    retrieved = [o.persona for o in asks if "D-04-S3" in o.retrieved_keys or SPECIAL in o.response_canaries()]
    audit_hits = SPECIAL in str(ctx.obs.raw_audit_table())
    log_hits, _ = ctx.obs.log_hits([SPECIAL], ctx.started_ms)
    excluded = report.get("special_category_excluded", [])
    passed = excluded == ["D-04-S3"] and not in_tiers and not objects and not retrieved and not audit_hits and not log_hits
    return passed, f"excluded at ingestion {excluded}; chunks {len(in_tiers)}; section objects {objects}; retrieved/answered " \
        f"for {retrieved}; audit hits {audit_hits}; log hits {log_hits}", \
        {"ingestion_excluded": excluded, "asks": [o.view() for o in asks],
         "model_inputs": "model inputs are built only from verified chunks retrieved from the tiers, which hold no such chunk"}


@test("TST-DATA-005", "data", ["DATA-003", "DATA-007"], ["CTL-008"], "L3",
      "Every chunk carries document, section, label, scope and version equal to its record; no chunk spans sections or "
      "is less restrictive than its document")
def data_005(ctx):
    inventory = ctx.marks.get("inventory") or _inventory(ctx)
    records = {}
    problems, covered = [], set()
    for chunk in _chunks(inventory):
        key = f"{chunk['document_id']}-{chunk['section_id']}"
        expected = ctx.oracle.get(key)
        if not all(chunk.get(k) for k in ("document_id", "section_id", "label", "scope", "record_version")):
            problems.append({"chunk": chunk["vector_id"], "problem": "attributes missing"})
            continue
        if expected is None or not expected["indexed"]:
            problems.append({"chunk": chunk["vector_id"], "section": key, "problem": "section should not be indexed"})
            continue
        covered.add(key)
        if chunk["document_id"] not in records:
            item = ctx.obs.classification_item(chunk["document_id"])
            records[chunk["document_id"]] = (item or {}).get("version"), __import__("json").loads((item or {}).get("record", "{}"))
        version, record = records[chunk["document_id"]]
        if (chunk["label"], chunk["scope"]) != (expected["label"], expected["scope"]):
            problems.append({"section": key, "tier": chunk["tier"], "problem": "attributes differ from the record",
                             "indexed": [chunk["label"], chunk["scope"]], "record": [expected["label"], expected["scope"]]})
        if chunk["record_version"] != str(version):
            problems.append({"section": key, "problem": "record version differs", "indexed": chunk["record_version"],
                             "record": version})
        foreign = [c for c in chunk["canaries"] if c != expected["canary"]]
        if foreign:
            problems.append({"section": key, "problem": "chunk spans sections", "foreign_canaries": foreign})
        document_label = record.get("document_label")
        if chunk["label"] not in RESTRICTIVENESS or (document_label in RESTRICTIVENESS
                                                     and RESTRICTIVENESS[chunk["label"]] < RESTRICTIVENESS[document_label]):
            problems.append({"section": key, "problem": "less restrictive than its document"})
    missing = sorted(k for k, e in ctx.oracle.items() if e["indexed"] and k not in covered)
    if missing:
        problems.append({"problem": "indexed sections without chunks", "sections": missing})
    return not problems, f"{len(_chunks(inventory))} chunks checked; problems: {problems[:6]}", \
        {"chunks_checked": len(_chunks(inventory)), "problems": problems}


@test("TST-DATA-006", "data", ["DATA-006"], ["CTL-010", "CTL-017"], "L3",
      "Shared tier holds no RESTRICTED section, restricted tier only RESTRICTED; no cache resource or cached answer path")
def data_006(ctx):
    inventory = ctx.marks.get("inventory") or _inventory(ctx)
    problems = []
    for chunk in _chunks(inventory):
        key = f"{chunk['document_id']}-{chunk['section_id']}"
        authoritative_tier = (ctx.oracle.get(key) or {}).get("tier")
        if chunk["tier"] == "shared" and chunk["label"] not in ("INTERNAL", "CONFIDENTIAL"):
            problems.append({"section": key, "problem": f"label {chunk['label']} in shared tier"})
        if chunk["tier"] == "restricted" and chunk["label"] != "RESTRICTED":
            problems.append({"section": key, "problem": f"label {chunk['label']} in restricted tier"})
        if authoritative_tier != chunk["tier"]:
            problems.append({"section": key, "problem": f"authoritative tier {authoritative_tier}, found in {chunk['tier']}"})
    for tier, content in inventory.items():
        for object_key in content["section_objects"]:
            parts = object_key.split("/")
            key = f"{parts[1]}-{parts[2].split('.')[0]}" if len(parts) == 3 else object_key
            if (ctx.oracle.get(key) or {}).get("tier") != tier:
                problems.append({"object": object_key, "problem": f"section object in the {tier} bucket"})
    t = ctx.target
    resources = t.client("cloudformation").describe_stack_resources(StackName=t.stack_name)["StackResources"]
    cache_types = sorted({r["ResourceType"] for r in resources if any(s in r["ResourceType"] for s in
                                                                     ("ElastiCache", "DAX", "MemoryDB", "CacheCluster"))})
    environment = t.client("lambda").get_function_configuration(FunctionName=t.outputs["QueryFunctionName"])["Environment"]["Variables"]
    cache_settings = sorted(k for k in environment if "CACHE" in k.upper())
    if cache_types or cache_settings:
        problems.append({"problem": "cache found", "resource_types": cache_types, "settings": cache_settings})
    return not problems, f"problems: {problems[:6]}; cache resources {cache_types}; cache settings {cache_settings}", \
        {"problems": problems, "stack_resource_types": sorted({r["ResourceType"] for r in resources}),
         "query_function_environment_keys": sorted(environment),
         "no_cache_behaviour": "TST-ELG-003 asks P-02's question again for six ineligible personas immediately afterwards"}
