#!/usr/bin/env python3
"""Deployment operations for the Episode 02 learner implementation: preflight · build · deploy · cleanup · outputs.

Non-interactive and guarded:
  * every AWS command shows the target account and refuses a mismatch with TLA_EXPECTED_ACCOUNT (config/learner.env);
  * `build normal` refuses to package any failure-experiment code;
  * a failure-experiment variant is built from the normal source with exactly ONE module replaced, deployed under its
    own stack name only when TLA_SENSITIVITY_RUN=1, and refused while another variant exists;
  * cleanup removes variants first, then the normal deployment.
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
    "normal": ("tla-s01e02-normal", None),
    "eligibility-removed": ("tla-s01e02-sen-eligibility", ("core/constraints.py", "eligibility_removed.py")),
    "labels-corrupted": ("tla-s01e02-sen-labels", ("core/sections.py", "labels_corrupted.py")),
    "claims-as-grants": ("tla-s01e02-sen-claims", ("query/policy_decision.py", "claims_as_grants.py")),
}
PACKAGES = {"query": ("core", "adapters", "query"), "ingestion": ("core", "adapters", "ingestion")}


# ── configuration and guards ────────────────────────────────────────────────────────────────────────────────────────
def load_config():
    config = {"AWS_PROFILE": "", "AWS_REGION": "us-east-1", "TLA_EXPECTED_ACCOUNT": "", "TLA_ROLE_PATH": "/tla/s01e02/",
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


def tags(variant):
    return [{"Key": k, "Value": v} for k, v in {
        "Project": "CloudBreweryLabs", "Course": "ThinkLikeAnArchitect", "Season": "01", "Episode": "02",
        "Environment": "Sandbox", "ManagedBy": "CloudBreweryLabs",
        "Variant": "normal" if variant == "normal" else "sensitivity", "Purpose": "education",
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
    print(f"existing Episode 02 stacks: {stacks or 'none'}")
    if any(v != "normal" for v in stacks):
        problems.append(f"a failure-experiment deployment still exists: {sorted(v for v in stacks if v != 'normal')} "
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
    expected = [] if variant == "normal" else [VARIANTS[variant][1][0]]
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
    manifest = {"schema": "tla-e02-build/1", "variant": variant, "replaced_modules": replaced,
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
    config = load_config()
    manifest_path = os.path.join(BUILD, variant, "manifest.json")
    if not os.path.exists(manifest_path):
        sys.exit(f"REFUSED: no build for '{variant}'. Run: python3 scripts/tla_ops.py build {variant}")
    with open(manifest_path, encoding="utf-8") as handle:
        manifest = json.load(handle)
    if manifest["variant"] != variant:
        sys.exit("REFUSED: build manifest variant mismatch")
    if variant != "normal" and os.environ.get("TLA_SENSITIVITY_RUN") != "1":
        sys.exit("REFUSED: failure-experiment variants are deployed only by the experiment runner")
    sess = session(config)
    account = account_guard(config, sess)
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
                  "QueryCodeKey": keys["query"], "IngestionCodeKey": keys["ingestion"],
                  "RolePath": config["TLA_ROLE_PATH"], "PermissionsBoundaryArn": config["TLA_PERMISSIONS_BOUNDARY_ARN"]}
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
        print(f"creating stack {n['stack']} …")
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
    print(f"deployed {n['stack']} ({stack['StackStatus']}) in {int(time.time() - started)} s")
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
    for attempt in range(2):
        cfn.delete_stack(StackName=stack_id, **({} if attempt == 0 else {"RetainResources": retain}))
        final = _wait_stack(cfn, stack_id)
        if final["StackStatus"] == "DELETE_COMPLETE":
            return "DELETE_COMPLETE" + (" (retained never-created roles)" if attempt else "")
        # Documented limitation: a role that was never created can block deletion. Retain it only if IAM confirms it
        # does not exist; anything else is reported, never hidden.
        retain = []
        for resource in cfn.describe_stack_resources(StackName=stack_id)["StackResources"]:
            if resource["ResourceStatus"] == "DELETE_FAILED":
                if resource["ResourceType"] != "AWS::IAM::Role":
                    return f"DELETE_FAILED: {resource['LogicalResourceId']} {resource.get('ResourceStatusReason', '')[:200]}"
                try:
                    iam.get_role(RoleName=resource.get("PhysicalResourceId") or resource["LogicalResourceId"])
                    return f"DELETE_FAILED: role {resource['LogicalResourceId']} still exists"
                except iam.exceptions.NoSuchEntityException:
                    retain.append(resource["LogicalResourceId"])
    return "DELETE_FAILED"


def cleanup(sess, account, variants):
    """Returns (failed, lines). Variants are always removed before the normal deployment."""
    s3, cfn = sess.client("s3"), sess.client("cloudformation")
    ordered = [v for v in VARIANTS if v != "normal" and v in variants] + (["normal"] if "normal" in variants else [])
    failed, lines = False, []
    for variant in ordered:
        n = names(variant, account)
        for suffix in ("records", "shared-sections", "restricted-sections"):
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
    variants = list(VARIANTS) if args.variant == "all" else [args.variant]
    failed, lines = cleanup(sess, account, variants)
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


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("preflight").set_defaults(func=cmd_preflight)
    for name, func in (("build", cmd_build), ("deploy", cmd_deploy), ("outputs", cmd_outputs)):
        p = sub.add_parser(name)
        p.add_argument("variant", choices=list(VARIANTS))
        p.set_defaults(func=func)
    p = sub.add_parser("cleanup")
    p.add_argument("--variant", choices=list(VARIANTS) + ["all"], default="all")
    p.set_defaults(func=cmd_cleanup)
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
