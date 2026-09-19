#!/usr/bin/env python3
"""Deployment operations for the Episode 03 learner implementation: preflight · build · deploy · cleanup · outputs.

Non-interactive and guarded:
  * every AWS command shows the target account and refuses a mismatch with TLA_EXPECTED_ACCOUNT (config/learner.env);
  * `build normal` refuses to package any failure-experiment code;
  * a failure-experiment variant is built from the normal source with exactly ONE module replaced, deployed under its
    own stack name only when TLA_SENSITIVITY_RUN=1, and refused while another variant exists;
  * cleanup removes variants first, then the normal deployment;
  * the learner lab (`lab-up` / `lab-down`) runs on its own two stacks, never on the normal deployment.
Requires Python 3.10+ and boto3. Credentials come from the standard AWS credential chain; nothing secret is stored.
"""
import argparse
import hashlib
import io
import json
import os
import re
import shutil
import sys
import time
import zipfile
from datetime import datetime, timezone

IMPLEMENTATION = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
EPISODE = os.path.dirname(IMPLEMENTATION)
APP = os.path.join(IMPLEMENTATION, "app")
SENSITIVITY = os.path.join(EPISODE, "06-validation", "sensitivity")
TEMPLATE = os.path.join(IMPLEMENTATION, "infrastructure", "template.yaml")
BUILD = os.path.join(IMPLEMENTATION, "build")
MODELS = ("amazon.titan-embed-text-v2:0", "amazon.nova-micro-v1:0")
VARIANT_MARKER = b"SENSITIVITY VARIANT"

# variant → (stack / name prefix, (module replaced in the package, test-only replacement))
VARIANTS = {
    "normal": ("tla-s01e03-normal", None),
    "status-ignored": ("tla-s01e03-fx-status", ("core/record_state.py", "status_ignored.py")),
    "order-ignored": ("tla-s01e03-fx-order", ("core/change_apply.py", "order_ignored.py")),
    "no-reconciliation": ("tla-s01e03-fx-reconciliation", ("change/reconciler.py", "no_reconciliation.py")),
    # Configuration-only: normal packages, normal reconciler, delivery disabled from creation (see
    # CONFIGURATION_VARIANTS). It must NOT reuse no-reconciliation, which also breaks the reconciler and so could
    # never show that WORKING reconciliation detects the lost change.
    "no-delivery": ("tla-s01e03-fx-nodelivery", None),
    # The learner lab: two configuration-only deployments of the NORMAL code, one per part of the lab. They carry
    # their own stack names so a learner's lab never touches, and is never confused with, the normal deployment.
    "lab-delivery-off": ("tla-s01e03-lab-off", None),
    "lab-delivery-on": ("tla-s01e03-lab-on", None),
}
PACKAGES = {"query": ("core", "adapters", "query"), "change": ("core", "adapters", "change")}
# Buckets the stack creates whose objects must be removed before deletion.
STACK_BUCKET_SUFFIXES = ("records", "shared-sections", "restricted-sections")


# ── configuration and guards ────────────────────────────────────────────────────────────────────────────────────────
def load_config():
    config = {"AWS_PROFILE": "", "AWS_REGION": "us-east-1", "TLA_EXPECTED_ACCOUNT": "", "TLA_ROLE_PATH": "/tla/s01e03/",
              "TLA_PERMISSIONS_BOUNDARY_ARN": "", "TLA_BUDGET_NAME": "", "TLA_RELEVANCE_MIN_SCORE": ""}
    path = os.path.join(IMPLEMENTATION, "config", "learner.env")
    if os.path.exists(path):
        with open(path, encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    config[key.strip()] = value.strip()
    for key in config:
        if os.environ.get(key):
            config[key] = os.environ[key]
    return config


def session(config):
    import boto3
    return boto3.Session(profile_name=config["AWS_PROFILE"] or None, region_name=config["AWS_REGION"])


def account_guard(config, sess, quiet=False):
    identity = sess.client("sts").get_caller_identity()
    account = identity["Account"]
    if not quiet:
        print(f"target account <redacted> · region {sess.region_name} · caller {identity['Arn'].split(':', 5)[5]}")
    expected = config.get("TLA_EXPECTED_ACCOUNT")
    if not expected:
        sys.exit("REFUSED: set TLA_EXPECTED_ACCOUNT in config/learner.env so commands cannot target the wrong account")
    if expected != account:
        sys.exit("REFUSED: the credentials belong to a different account than TLA_EXPECTED_ACCOUNT")
    return account


def names(variant, account):
    prefix = VARIANTS[variant][0]
    return {"prefix": prefix, "stack": prefix, "artifact_bucket": f"{prefix}-artifacts-{account}"}


# FX-3's variant must be created with the change signal already off: its experiment requires a deployment where the
# low-latency path NEVER accounted for a change. Disabling the mapping at runtime is what proved unreliable,
# so the condition is established by the deployment itself. Kept as an explicit set rather than a third element in
# VARIANTS, whose tuple shape is indexed positionally in several places and asserted by the deployment-guard tests.
DELIVERY_DISABLED_AT_CREATION = frozenset({"no-reconciliation", "no-delivery", "lab-delivery-off"})

# Variants whose ONLY intentional difference from normal is stack configuration — they replace no application module
# and run the normal code, including the normal reconciler. Declaring them explicitly is what keeps "zero replaced
# modules" from silently becoming a way to pass the build guard: a non-normal variant that replaces nothing and is not
# named here is REFUSED (an earlier change). `no-delivery` exists because reconciliation must be tested on a deployment where the change signal
# was never active, and runtime suppression of the normal deployment cannot establish that.
CONFIGURATION_VARIANTS = frozenset({"no-delivery", "lab-delivery-off", "lab-delivery-on"})

# Learner lab parts → the deployment each one runs on. Part A needs delivery OFF FROM CREATION, because switching it
# off on a running deployment was shown to be unreliable; Part B needs live delivery, because only the notifier
# classifies an upward reclassification (0 s window). Neither is ever an evidence environment.
LAB_PARTS = {"delivery-off": "lab-delivery-off", "delivery-on": "lab-delivery-on"}
LAB_VARIANTS = frozenset(LAB_PARTS.values())


def change_notifications_enabled(variant):
    """The `ChangeNotificationsEnabled` stack parameter for this variant, as CloudFormation expects it.

    Everything except FX-3's variant is created delivering. The normal deployment is never created with delivery off:
    a baseline that never received a notification would prove nothing about a system whose whole subject is change.
    """
    return "false" if variant in DELIVERY_DISABLED_AT_CREATION else "true"


def tags(variant):
    return [{"Key": k, "Value": v} for k, v in {
        "Project": "CloudBreweryLabs", "Course": "ThinkLikeAnArchitect", "Season": "01", "Episode": "03",
        "Environment": "Sandbox", "ManagedBy": "CloudBreweryLabs",
        "Variant": "normal" if variant == "normal" else "lab" if variant in LAB_VARIANTS else "sensitivity",
        "Purpose": "education",
        "DeployedWith": "CloudFormation"}.items()]


def sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()


def existing_stacks(cfn):
    found = {}
    for variant, (stack, _) in VARIANTS.items():
        try:
            found[variant] = cfn.describe_stacks(StackName=stack)["Stacks"][0]["StackStatus"]
        except Exception:  # noqa: BLE001
            pass
    return found


# ── preflight ───────────────────────────────────────────────────────────────────────────────────────────────────────
def cmd_preflight(args):
    config = load_config()
    problems = []
    if sys.version_info < (3, 10):
        problems.append(f"Python 3.10+ required (found {sys.version.split()[0]})")
    try:
        import boto3
        print(f"python {sys.version.split()[0]} · boto3 {boto3.__version__}")
    except ImportError:
        sys.exit("REFUSED: boto3 is not installed (pip install boto3)")
    sess = session(config)
    account_guard(config, sess)
    if sess.region_name != "us-east-1":
        problems.append(f"region {sess.region_name} is not the verified region us-east-1 (In-Region models)")
    bedrock = sess.client("bedrock")
    for model in MODELS:
        try:
            a = bedrock.get_foundation_model_availability(modelId=model)
            state = {k: a.get(k) for k in ("authorizationStatus", "entitlementAvailability", "regionAvailability")}
            print(f"model {model}: {state}")
            if state != {"authorizationStatus": "AUTHORIZED", "entitlementAvailability": "AVAILABLE",
                         "regionAvailability": "AVAILABLE"}:
                problems.append(f"model {model} is not usable In-Region: {state}")
        except Exception as error:  # noqa: BLE001
            problems.append(f"could not read availability of {model}: {type(error).__name__}")
    try:
        logging_config = bedrock.get_model_invocation_logging_configuration().get("loggingConfig") or {}
        enabled = bool(logging_config.get("cloudWatchConfig") or logging_config.get("s3Config"))
        print(f"model invocation logging: {'ENABLED' if enabled else 'disabled'}")
        if enabled:
            problems.append("model invocation logging is enabled: prompts with section text would be copied into logs")
    except Exception as error:  # noqa: BLE001
        problems.append(f"could not read model invocation logging configuration: {type(error).__name__}")
    try:
        sess.client("s3vectors").list_vector_buckets(maxResults=1)
        print("S3 Vectors: reachable")
    except Exception as error:  # noqa: BLE001
        problems.append(f"S3 Vectors not reachable: {type(error).__name__}")
    stacks = existing_stacks(sess.client("cloudformation"))
    print(f"existing Episode 03 stacks: {stacks or 'none'}")
    labs = sorted(v for v in stacks if v in LAB_VARIANTS)
    if labs:
        problems.append(f"a lab deployment is still running: {labs} — end it with lab-down before anything else")
    if any(v != "normal" and v not in LAB_VARIANTS for v in stacks):
        problems.append(f"a failure-experiment deployment still exists: "
                        f"{sorted(v for v in stacks if v != 'normal' and v not in LAB_VARIANTS)} "
                        "— run cleanup before anything else")
    if config.get("TLA_BUDGET_NAME"):
        try:
            account = sess.client("sts").get_caller_identity()["Account"]
            budget = sess.client("budgets").describe_budget(AccountId=account, BudgetName=config["TLA_BUDGET_NAME"])["Budget"]
            print(f"budget: found, limit {budget['BudgetLimit']['Amount']} {budget['BudgetLimit']['Unit']}")
        except Exception as error:  # noqa: BLE001
            problems.append(f"the configured budget is not readable: {type(error).__name__}")
    else:
        print("budget: TLA_BUDGET_NAME not set — create an AWS Budget with alerts before deploying (COST_AND_CLEANUP.md)")
    for problem in problems:
        print(f"PREFLIGHT FAIL  {problem}")
    print("preflight: " + ("PASS" if not problems else "FAIL"))
    return 0 if not problems else 1


# ── build ───────────────────────────────────────────────────────────────────────────────────────────────────────────
def _stage(variant):
    staging = os.path.join(BUILD, variant, "staging")
    shutil.rmtree(os.path.join(BUILD, variant), ignore_errors=True)
    shutil.copytree(APP, staging, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    replacement = VARIANTS[variant][1]
    if replacement:
        shutil.copyfile(os.path.join(SENSITIVITY, replacement[1]), os.path.join(staging, *replacement[0].split("/")))
    with open(os.path.join(staging, "adapters", "build_info.py"), "w", encoding="utf-8") as handle:
        handle.write('"""Build-time constant, rewritten by scripts/tla_ops.py build. It labels audit records; it never '
                     f'changes behaviour."""\nVARIANT = "{variant}"\n')
    return staging


def _staged_files(staging):
    for directory, _, files in os.walk(staging):
        for name in sorted(files):
            path = os.path.join(directory, name)
            yield os.path.relpath(path, staging).replace(os.sep, "/"), path


def _guard(variant, staging):
    """Normal: byte-identical to app/ (except build_info) and no variant marker. Variant: exactly one module differs."""
    differing = []
    for relative, path in _staged_files(staging):
        with open(path, "rb") as handle:
            data = handle.read()
        source = os.path.join(APP, *relative.split("/"))
        if relative == "adapters/build_info.py":
            continue
        with open(source, "rb") as handle:
            if handle.read() != data:
                differing.append(relative)
        if variant == "normal" and VARIANT_MARKER in data:
            sys.exit(f"REFUSED: normal build contains failure-experiment code: {relative}")
    replacement = VARIANTS[variant][1]
    if variant != "normal" and replacement is None and variant not in CONFIGURATION_VARIANTS:
        sys.exit(f"REFUSED: variant {variant} replaces no application module and is not a declared configuration "
                 f"variant — zero replacement is legitimate only for {sorted(CONFIGURATION_VARIANTS)}")
    expected = [] if replacement is None else [replacement[0]]
    if differing != expected:
        sys.exit(f"REFUSED: build {variant} differs from app/ in {differing}, expected {expected}")
    return differing


def _zip(staging, packages, target):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for relative, path in sorted(_staged_files(staging)):
            if relative.split("/")[0] in packages and relative.endswith(".py"):
                info = zipfile.ZipInfo(relative, date_time=(1980, 1, 1, 0, 0, 0))
                info.external_attr = 0o644 << 16
                info.compress_type = zipfile.ZIP_DEFLATED
                with open(path, "rb") as handle:
                    archive.writestr(info, handle.read())
    data = buffer.getvalue()
    with open(target, "wb") as handle:
        handle.write(data)
    return {"file": os.path.basename(target), "sha256": sha256_bytes(data)}


def cmd_build(args):
    variant = args.variant
    staging = _stage(variant)
    replaced = _guard(variant, staging)
    out = os.path.join(BUILD, variant)
    manifest = {"schema": "tla-e03-build/1", "variant": variant, "replaced_modules": replaced,
                "packages": {fn: _zip(staging, parts, os.path.join(out, f"{fn}.zip")) for fn, parts in PACKAGES.items()}}
    with open(os.path.join(out, "manifest.json"), "w", encoding="utf-8") as handle:
        json.dump(manifest, handle, indent=2)
    for fn, package in manifest["packages"].items():
        print(f"built {variant}/{fn}.zip sha256 {package['sha256']}")
    if replaced:
        print(f"NOTE: failure-experiment build — {replaced[0]} is replaced. Deploy only through the experiment runner.")
    return 0


# ── deploy ──────────────────────────────────────────────────────────────────────────────────────────────────────────
def _retry_transient(call, attempts=12, delay=5):
    """S3 can briefly answer NoSuchBucket / OperationAborted right after a bucket name is re-created."""
    for attempt in range(attempts):
        try:
            return call()
        except Exception as error:  # noqa: BLE001
            text = f"{type(error).__name__} {error}"
            if attempt == attempts - 1 or not any(code in text for code in ("NoSuchBucket", "OperationAborted")):
                raise
            time.sleep(delay)


def _ensure_artifact_bucket(s3, bucket, variant):
    try:
        s3.head_bucket(Bucket=bucket)
    except Exception:  # noqa: BLE001
        def create():
            try:
                s3.create_bucket(Bucket=bucket)
            except Exception as error:  # noqa: BLE001
                if "BucketAlreadyOwnedByYou" not in f"{type(error).__name__} {error}":
                    raise
        _retry_transient(create)
    _retry_transient(lambda: s3.put_public_access_block(Bucket=bucket, PublicAccessBlockConfiguration={
        "BlockPublicAcls": True, "IgnorePublicAcls": True, "BlockPublicPolicy": True, "RestrictPublicBuckets": True}))
    _retry_transient(lambda: s3.put_bucket_policy(Bucket=bucket, Policy=json.dumps({"Version": "2012-10-17", "Statement": [{
        "Sid": "DenyInsecureTransport", "Effect": "Deny", "Principal": "*", "Action": "s3:*",
        "Resource": [f"arn:aws:s3:::{bucket}", f"arn:aws:s3:::{bucket}/*"],
        "Condition": {"Bool": {"aws:SecureTransport": "false"}}}]})))
    _retry_transient(lambda: s3.put_bucket_tagging(Bucket=bucket, Tagging={"TagSet": tags(variant)}))


def _wait_stack(cfn, stack_id):
    while True:
        stack = cfn.describe_stacks(StackName=stack_id)["Stacks"][0]
        if not stack["StackStatus"].endswith("_IN_PROGRESS"):
            return stack
        time.sleep(10)


def _failure_events(cfn, stack_id):
    return [f"{e['LogicalResourceId']}: {e.get('ResourceStatusReason', '')[:300]}"
            for e in cfn.describe_stack_events(StackName=stack_id)["StackEvents"]
            if e["ResourceStatus"].endswith("FAILED") and "cancelled" not in e.get("ResourceStatusReason", "")][:10]


def cmd_deploy(args):
    variant = args.variant
    if variant in LAB_VARIANTS:
        sys.exit(f"REFUSED: lab deployments are started with lab-up, e.g. python3 scripts/tla_ops.py lab-up "
                 f"{next(p for p, v in LAB_PARTS.items() if v == variant)}")
    return deploy(variant)


def deploy(variant, quiet=False):
    """Deploy a built variant. Experiment variants need the runner's flag; lab variants arrive only through lab-up."""
    config = load_config()
    manifest_path = os.path.join(BUILD, variant, "manifest.json")
    if not os.path.exists(manifest_path):
        sys.exit(f"REFUSED: no build for '{variant}'. Run: python3 scripts/tla_ops.py build {variant}")
    with open(manifest_path, encoding="utf-8") as handle:
        manifest = json.load(handle)
    if manifest["variant"] != variant:
        sys.exit("REFUSED: build manifest variant mismatch")
    if variant != "normal" and variant not in LAB_VARIANTS and os.environ.get("TLA_SENSITIVITY_RUN") != "1":
        sys.exit("REFUSED: failure-experiment variants are deployed only by the experiment runner")
    sess = session(config)
    account = account_guard(config, sess, quiet=quiet)
    s3, cfn = sess.client("s3"), sess.client("cloudformation")
    others = [v for v in existing_stacks(cfn) if v not in ("normal", variant)]
    if variant != "normal" and others:
        sys.exit(f"REFUSED: only one failure-experiment deployment may exist at a time (found {others})")
    n = names(variant, account)
    _ensure_artifact_bucket(s3, n["artifact_bucket"], variant)
    keys = {}
    for fn, package in manifest["packages"].items():
        keys[fn] = f"functions/{package['sha256']}/{fn}.zip"
        s3.upload_file(os.path.join(BUILD, variant, package["file"]), n["artifact_bucket"], keys[fn])
    parameters = {"NamePrefix": n["prefix"], "Variant": variant, "ArtifactBucket": n["artifact_bucket"],
                  "QueryCodeKey": keys["query"], "ChangeCodeKey": keys["change"],
                  "RolePath": config["TLA_ROLE_PATH"], "PermissionsBoundaryArn": config["TLA_PERMISSIONS_BOUNDARY_ARN"],
                  "ChangeNotificationsEnabled": change_notifications_enabled(variant)}
    if config.get("TLA_RELEVANCE_MIN_SCORE"):
        parameters["RelevanceMinScore"] = config["TLA_RELEVANCE_MIN_SCORE"]
    with open(TEMPLATE, encoding="utf-8") as handle:
        body = handle.read()
    common = {"StackName": n["stack"], "TemplateBody": body, "Capabilities": ["CAPABILITY_NAMED_IAM"], "Tags": tags(variant),
              "Parameters": [{"ParameterKey": k, "ParameterValue": v} for k, v in parameters.items()]}
    started = time.time()
    try:
        existing = cfn.describe_stacks(StackName=n["stack"])["Stacks"][0]
    except Exception:  # noqa: BLE001
        existing = None
    if existing is None:
        stack_id = cfn.create_stack(OnFailure="DELETE", **common)["StackId"]
        print(f"creating stack {n['stack']} … (about 2–3 minutes)")
    else:
        try:
            stack_id = cfn.update_stack(**common)["StackId"]
            print(f"updating stack {n['stack']} …")
        except Exception as error:  # noqa: BLE001
            if "No updates are to be performed" not in str(error):
                raise
            stack_id = existing["StackId"]
            print(f"stack {n['stack']} already up to date")
    stack = _wait_stack(cfn, stack_id)
    if stack["StackStatus"] not in ("CREATE_COMPLETE", "UPDATE_COMPLETE"):
        for line in _failure_events(cfn, stack_id):
            print(f"  FAILED {line}")
        sys.exit(f"DEPLOY FAILED: {n['stack']} {stack['StackStatus']}")
    # Immutable identity, written at the moment of deployment. A stack NAME is reused: the canonical normal stack was
    # destroyed and rebuilt under the same name, and no recorded field could afterwards tell the two apart. These
    # fields can never be reused, so a later result can always be attributed to the deployment that produced it.
    # Read back from the DEPLOYED stack, never from `parameters` above: the latter is what this process intended to
    # send, and a variant's premise must rest on what CloudFormation actually holds. Absent means null, never guessed.
    deployed = {p["ParameterKey"]: p.get("ParameterValue") for p in stack.get("Parameters", [])}
    identity = {"schema": "tla-e03-deployment/2", "stack_name": n["stack"], "stack_id": stack["StackId"],
                "stack_created": str(stack.get("CreationTime")), "stack_status": stack["StackStatus"],
                "variant": variant, "replaced_modules": manifest.get("replaced_modules"),
                "change_notifications_enabled": deployed.get("ChangeNotificationsEnabled"),
                "package_sha256": {fn: package["sha256"] for fn, package in manifest["packages"].items()},
                "deployed_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}
    with open(os.path.join(BUILD, variant, "deployed.json"), "w", encoding="utf-8") as handle:
        json.dump(identity, handle, indent=2, sort_keys=True)
    print(f"deployed {n['stack']} ({stack['StackStatus']}) in {int(time.time() - started)} s")
    if not quiet:
        print(f"  stack id     {identity['stack_id']}")
        print(f"  created      {identity['stack_created']}")
        print(f"  packages     {identity['package_sha256']}")
    return 0


# ── cleanup ─────────────────────────────────────────────────────────────────────────────────────────────────────────
def _empty_bucket(s3, bucket):
    removed = 0
    try:
        for page in s3.get_paginator("list_object_versions").paginate(Bucket=bucket):
            keys = [{"Key": o["Key"], "VersionId": o["VersionId"]} for o in page.get("Versions", []) + page.get("DeleteMarkers", [])]
            for start in range(0, len(keys), 1000):
                s3.delete_objects(Bucket=bucket, Delete={"Objects": keys[start:start + 1000], "Quiet": True})
                removed += len(keys[start:start + 1000])
    except Exception as error:  # noqa: BLE001
        if "NoSuchBucket" not in str(error):
            raise
    return removed


def _delete_stack(sess, stack):
    cfn, iam = sess.client("cloudformation"), sess.client("iam")
    try:
        current = cfn.describe_stacks(StackName=stack)["Stacks"][0]
    except Exception:  # noqa: BLE001
        return "not present"
    stack_id, retain = current["StackId"], []
    for attempt in range(4):
        cfn.delete_stack(StackName=stack_id, **({} if attempt == 0 else {"RetainResources": retain}))
        final = _wait_stack(cfn, stack_id)
        if final["StackStatus"] == "DELETE_COMPLETE":
            return "DELETE_COMPLETE" + (" (retained never-created roles)" if retain else "")
        retain = []
        for resource in cfn.describe_stack_resources(StackName=stack_id)["StackResources"]:
            if resource["ResourceStatus"] == "DELETE_FAILED":
                reason = resource.get("ResourceStatusReason", "")
                # Objects reappear between emptying a bucket and deleting the stack, because the stack's own writers
                # are still alive while it comes down — measured: 15 shared and 2 restricted objects returned between
                # the two steps. Empty it again and retry. Giving up here leaves a deliberately broken variant
                # deployment running, which §11 forbids and which costs money quietly.
                if resource["ResourceType"] == "AWS::S3::Bucket" and "not empty" in reason:
                    _empty_bucket(sess.client("s3"), resource.get("PhysicalResourceId") or "")
                    continue
                if resource["ResourceType"] != "AWS::IAM::Role":
                    return f"DELETE_FAILED: {resource['LogicalResourceId']} {reason[:200]}"
                try:
                    iam.get_role(RoleName=resource.get("PhysicalResourceId") or resource["LogicalResourceId"])
                    return f"DELETE_FAILED: role {resource['LogicalResourceId']} still exists"
                except iam.exceptions.NoSuchEntityException:
                    retain.append(resource["LogicalResourceId"])
    return "DELETE_FAILED"


def cleanup(sess, account, variants, allow_normal=False):
    """Returns (failed, lines). Variants are always removed before the normal deployment.

    Destroying the canonical `normal` deployment requires `allow_normal=True`, passed deliberately by a caller that
    means it. The guard lives HERE rather than only in the command line, because every path reaches this function —
    including a failure-path cleanup in a runner, which is how the canonical environment was once destroyed by an
    argument that was merely absent. An omitted argument must never mean "delete everything".
    """
    if "normal" in variants and not allow_normal:
        raise RuntimeError("REFUSED: cleanup() will not destroy the canonical normal deployment unless the caller "
                           "passes allow_normal=True. Clean the experiment variants instead.")
    s3 = sess.client("s3")
    ordered = [v for v in VARIANTS if v != "normal" and v in variants] + (["normal"] if "normal" in variants else [])
    failed, lines = False, []
    for variant in ordered:
        n = names(variant, account)
        for suffix in STACK_BUCKET_SUFFIXES:
            bucket = f"{n['prefix']}-{suffix}-{account}"
            lines.append(f"[{variant}] {suffix} bucket objects removed: {_empty_bucket(s3, bucket)}")
        result = _delete_stack(sess, n["stack"])
        lines.append(f"[{variant}] stack {n['stack']}: {result}")
        failed |= result.startswith("DELETE_FAILED")
        removed = _empty_bucket(s3, n["artifact_bucket"])
        try:
            s3.delete_bucket(Bucket=n["artifact_bucket"])
            lines.append(f"[{variant}] artifact bucket: deleted ({removed} objects)")
        except Exception as error:  # noqa: BLE001
            missing = "NoSuchBucket" in str(error)
            lines.append(f"[{variant}] artifact bucket: " + ("not present" if missing else f"ERROR {type(error).__name__}"))
            failed |= not missing
    return failed, lines


def cmd_cleanup(args):
    config = load_config()
    sess = session(config)
    account = account_guard(config, sess)
    # The DEFAULT is the safe operation: experiment variants only. "all" and "normal" both require --destroy-normal,
    # so the destructive case is always something the operator typed on purpose.
    if args.variant == "experiments":
        variants = [v for v in VARIANTS if v != "normal"]
    elif args.variant == "all":
        variants = list(VARIANTS)
    else:
        variants = [args.variant]
    if "normal" in variants and not args.destroy_normal:
        sys.exit("REFUSED: destroying the canonical normal deployment needs --destroy-normal as well. "
                 "Without it, cleanup removes the experiment variants only.")
    failed, lines = cleanup(sess, account, variants, allow_normal=args.destroy_normal)
    for line in lines:
        print(line)
    print("cleanup: " + ("INCOMPLETE — see above" if failed else "done — now run: python3 -m harness verify-cleanup"))
    return 1 if failed else 0


def cmd_outputs(args):
    config = load_config()
    sess = session(config)
    account = account_guard(config, sess, quiet=True)
    stack = sess.client("cloudformation").describe_stacks(StackName=names(args.variant, account)["stack"])["Stacks"][0]
    print(json.dumps({o["OutputKey"]: re.sub(r"\d{12}", "<account>", o["OutputValue"]) for o in stack.get("Outputs", [])},
                     indent=2))
    return 0


def cmd_notifications(args):
    """Enable or disable the records-stream notifications (FX-3 drops them; reconciliation must still find the drift)."""
    config = load_config()
    sess = session(config)
    account = account_guard(config, sess, quiet=True)
    stack = sess.client("cloudformation").describe_stacks(StackName=names(args.variant, account)["stack"])["Stacks"][0]
    mapping = {o["OutputKey"]: o["OutputValue"] for o in stack.get("Outputs", [])}["RecordsStreamMappingId"]
    lam = sess.client("lambda")
    lam.update_event_source_mapping(UUID=mapping, Enabled=(args.state == "on"))
    for _ in range(30):
        state = lam.get_event_source_mapping(UUID=mapping)["State"]
        print(f"notifications {args.state}: mapping state {state}")
        if state in ("Enabled", "Disabled"):
            return 0
        time.sleep(5)
    return 1


# ── learner lab ─────────────────────────────────────────────────────────────────────────────────────────────────────
def _lab_module():
    """The learner-facing lab operations live beside the harness, which already knows how to load the corpus."""
    validation = os.path.join(EPISODE, "06-validation")
    if validation not in sys.path:
        sys.path.insert(0, validation)
    from harness import lab
    return lab


def lab_conflicts(existing, variant):
    """Deployments that must be gone before this lab part starts: the other part, or any experiment variant.

    One lab part at a time keeps the cost bounded and makes it impossible to run a Part B command against Part A.
    The normal deployment is not a conflict — the lab never touches it.
    """
    return sorted(v for v in existing if v not in ("normal", variant))


def cmd_lab_up(args):
    variant = LAB_PARTS[args.part]
    config = load_config()
    sess = session(config)
    account_guard(config, sess)
    conflicts = lab_conflicts(existing_stacks(sess.client("cloudformation")), variant)
    if conflicts:
        others = [p for p, v in LAB_PARTS.items() if v in conflicts]
        hint = f"python3 scripts/tla_ops.py lab-down {others[0]}" if others else "python3 scripts/tla_ops.py cleanup"
        sys.exit(f"REFUSED: another deployment is still running ({', '.join(conflicts)}). End it first: {hint}")
    started = time.time()
    print(f"[1/3] packaging the application ({args.part})")
    staging = _stage(variant)
    _guard(variant, staging)
    out = os.path.join(BUILD, variant)
    manifest = {"schema": "tla-e03-build/1", "variant": variant, "replaced_modules": [],
                "packages": {fn: _zip(staging, parts, os.path.join(out, f"{fn}.zip")) for fn, parts in PACKAGES.items()}}
    with open(os.path.join(out, "manifest.json"), "w", encoding="utf-8") as handle:
        json.dump(manifest, handle, indent=2)
    print(f"[2/3] deploying — change notifications "
          f"{'OFF from creation' if variant in DELIVERY_DISABLED_AT_CREATION else 'ON'}")
    deploy(variant, quiet=True)
    print("[3/3] loading the synthetic records system and building the index (about 3–4 minutes)")
    lab = _lab_module()
    code = lab.run(lab.prepare, part=args.part)
    print(f"lab-up {args.part}: {'READY' if code == 0 else 'NOT READY'} in {int(time.time() - started)} s")
    return code


def cmd_lab_down(args):
    variant = LAB_PARTS[args.part]
    config = load_config()
    sess = session(config)
    account = account_guard(config, sess)
    failed, lines = cleanup(sess, account, [variant])
    for line in lines:
        print(line)
    if failed:
        print(f"lab-down {args.part}: INCOMPLETE — run the same command again; if it persists see Troubleshooting")
        return 1
    _lab_module()                                   # puts the harness on the path
    from harness import cleanup_check  # noqa: E402
    clean, found, _ = cleanup_check.verify(sess, account, [variant])
    remaining = {kind: items for kind, items in found.items() if items}
    if not clean:
        print(f"still present: {json.dumps(remaining)}")
        print(f"lab-down {args.part}: INCOMPLETE — AWS can take a minute to finish deleting; run it again")
        return 1
    print(f"lab-down {args.part}: CLEAN — nothing from this part remains")
    print("  checked: stack, buckets, tables, functions, knowledge bases, vector stores, user pool, log groups, roles")
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("preflight").set_defaults(func=cmd_preflight)
    for name, func in (("build", cmd_build), ("deploy", cmd_deploy), ("outputs", cmd_outputs)):
        p = sub.add_parser(name)
        p.add_argument("variant", choices=list(VARIANTS))
        p.set_defaults(func=func)
    p = sub.add_parser("cleanup")
    p.add_argument("--variant", choices=list(VARIANTS) + ["all", "experiments"], default="experiments")
    p.add_argument("--destroy-normal", action="store_true",
                   help="required to destroy the canonical normal deployment; without it only variants are removed")
    p.set_defaults(func=cmd_cleanup)
    p = sub.add_parser("notifications")
    p.add_argument("state", choices=["on", "off"])
    p.add_argument("--variant", choices=list(VARIANTS), default="normal")
    p.set_defaults(func=cmd_notifications)
    for name, func, text in (("lab-up", cmd_lab_up, "start one part of the learner lab (build, deploy, load records)"),
                             ("lab-down", cmd_lab_down, "end one part of the learner lab and confirm nothing remains")):
        p = sub.add_parser(name, help=text)
        p.add_argument("part", choices=list(LAB_PARTS))
        p.set_defaults(func=func)
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
