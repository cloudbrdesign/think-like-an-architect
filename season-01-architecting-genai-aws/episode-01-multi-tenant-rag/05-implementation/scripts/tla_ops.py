#!/usr/bin/env python3
"""Deployment operations for the Episode 01 learner implementation: preflight · build · deploy · cleanup · outputs.

Called by the .sh wrappers in this directory. Non-interactive, idempotent, and guarded:
  - every command shows the target account and refuses a mismatch with TLA_EXPECTED_ACCOUNT (config/learner.env);
  - build.sh normal refuses to package anything from 06-validation/sensitivity/;
  - the sensitivity variant can only be built, deployed and cleaned up under its own stack name and tags.
Requires Python 3.10+ and boto3. Credentials come from the standard AWS credential chain; nothing secret is stored.
"""
import argparse
import base64
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
SENSITIVITY_SCOPE = os.path.join(EPISODE, "06-validation", "sensitivity", "retrieval_scope.py")
TEMPLATE = os.path.join(IMPLEMENTATION, "infrastructure", "template.yaml")
BUILD = os.path.join(IMPLEMENTATION, "build")
VARIANTS = ("normal", "sensitivity")
MODELS = ("amazon.titan-embed-text-v2:0", "amazon.nova-micro-v1:0")
PROFILE_PREFIX = re.compile(r"^(us|eu|apac|global|jp|au|ca|us-gov)\.")


# ── configuration and guards ────────────────────────────────────────────────────────────────────────────────────────
def load_config():
    config = {"AWS_PROFILE": "", "AWS_REGION": "us-east-1", "TLA_EXPECTED_ACCOUNT": "", "TLA_ROLE_PATH": "/tla/s01e01/",
              "TLA_PERMISSIONS_BOUNDARY_ARN": ""}
    path = os.path.join(IMPLEMENTATION, "config", "learner.env")
    if os.path.exists(path):
        for line in open(path, encoding="utf-8"):
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


def account_guard(config, sess):
    identity = sess.client("sts").get_caller_identity()
    account = identity["Account"]
    print(f"target account {account} · region {sess.region_name} · caller {identity['Arn'].split(':', 5)[5]}")
    expected = config.get("TLA_EXPECTED_ACCOUNT")
    if expected and expected != account:
        sys.exit(f"REFUSED: account {account} is not TLA_EXPECTED_ACCOUNT {expected}")
    return account


def names(variant, account):
    prefix = f"tla-s01e01-{variant}"
    return {"prefix": prefix, "stack": prefix, "artifact_bucket": f"{prefix}-artifacts-{account}"}


def tags(variant):
    return [{"Key": k, "Value": v} for k, v in {
        "Project": "CloudBreweryLabs", "Course": "ThinkLikeAnArchitect", "Season": "01", "Episode": "01",
        "Environment": "Sandbox", "ManagedBy": "CloudBreweryLabs", "Variant": variant, "Purpose": "education",
        "DeployedWith": "CloudFormation"}.items()]


def sha256_file(path):
    return hashlib.sha256(open(path, "rb").read()).hexdigest()


# ── preflight ───────────────────────────────────────────────────────────────────────────────────────────────────────
def model_access_problems(bedrock, region, models=MODELS, report=print):
    """VE-18: every required model must be authorised, entitled and available In-Region in the configured region.
    Returns learner-facing problems. It never substitutes another model or region: the lab uses exactly MODELS."""
    problems = []
    for model in models:
        try:
            availability = bedrock.get_foundation_model_availability(modelId=model)
            state = {k: availability.get(k) for k in ("authorizationStatus", "entitlementAvailability", "regionAvailability")}
            report(f"model {model}: {state}")
            if state != {"authorizationStatus": "AUTHORIZED", "entitlementAvailability": "AVAILABLE",
                         "regionAvailability": "AVAILABLE"}:
                problems.append(f"model {model} is not usable In-Region in {region}: {state}. This lab needs exactly this "
                                "model in this region and will not substitute another. If access has not been granted in "
                                "this account, enable it once in the Amazon Bedrock console (Model access), then re-run "
                                "scripts/preflight.sh before deploying (VE-18).")
        except Exception as error:  # noqa: BLE001
            problems.append(f"could not read the availability of {model} in {region}: {type(error).__name__}. Check that "
                            "your credentials may call bedrock:GetFoundationModelAvailability and that Amazon Bedrock "
                            "model access is enabled for this account and region, then re-run preflight (VE-18).")
    return problems


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
        print(f"WARNING: region {sess.region_name} is not the verified region us-east-1; In-Region model availability "
              "is checked below and the design requires it (CTL-023)")
    bedrock = sess.client("bedrock")
    problems += model_access_problems(bedrock, sess.region_name)
    try:
        logging_config = bedrock.get_model_invocation_logging_configuration().get("loggingConfig") or {}
        enabled = bool(logging_config.get("cloudWatchConfig") or logging_config.get("s3Config"))
        print(f"model invocation logging: {'ENABLED' if enabled else 'disabled'}")
        if enabled and not args.acknowledge_model_logging:
            problems.append("model invocation logging is enabled: prompts containing tenant content would be copied "
                            "into logs (CTL-024). Disable it, or re-run with --acknowledge-model-logging (recorded).")
    except Exception as error:  # noqa: BLE001
        problems.append(f"could not read model invocation logging configuration: {type(error).__name__}")
    try:
        sess.client("s3vectors").list_vector_buckets(maxResults=1)
        print("S3 Vectors: reachable")
    except Exception as error:  # noqa: BLE001
        problems.append(f"S3 Vectors not reachable in {sess.region_name}: {type(error).__name__}")
    cfn = sess.client("cloudformation")
    for variant in VARIANTS:
        stack = names(variant, "0")["stack"]
        try:
            status = cfn.describe_stacks(StackName=stack)["Stacks"][0]["StackStatus"]
            print(f"existing stack {stack}: {status}")
        except Exception:  # noqa: BLE001
            print(f"existing stack {stack}: none")
    template = open(TEMPLATE, encoding="utf-8").read()
    for model_id in re.findall(r"GENERATION_MODEL_ID:\s*(\S+)", template):
        if PROFILE_PREFIX.match(model_id):
            problems.append(f"template generation model {model_id} is a cross-region inference profile (CTL-023)")
    for problem in problems:
        print(f"PREFLIGHT FAIL  {problem}")
    print("preflight: " + ("PASS" if not problems else "FAIL"))
    return 0 if not problems else 1


# ── build ───────────────────────────────────────────────────────────────────────────────────────────────────────────
def _stage(variant):
    staging = os.path.join(BUILD, variant, "staging")
    shutil.rmtree(os.path.join(BUILD, variant), ignore_errors=True)
    shutil.copytree(APP, staging, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    if variant == "sensitivity":
        shutil.copyfile(SENSITIVITY_SCOPE, os.path.join(staging, "shared", "retrieval_scope.py"))
    with open(os.path.join(staging, "shared", "build_info.py"), "w", encoding="utf-8") as handle:
        handle.write('"""Build-time constant written by scripts/build.sh. It labels audit records; it never changes '
                     f'behaviour."""\nVARIANT = "{variant}"\n')
    return staging


def _guard_normal(staging):
    staged_scope = os.path.join(staging, "shared", "retrieval_scope.py")
    if sha256_file(staged_scope) != sha256_file(os.path.join(APP, "shared", "retrieval_scope.py")):
        sys.exit("REFUSED: normal build retrieval_scope.py is not byte-identical to app/shared/retrieval_scope.py")
    sensitivity_hash = sha256_file(SENSITIVITY_SCOPE)
    for directory, _, files in os.walk(staging):
        for name in files:
            path = os.path.join(directory, name)
            if sha256_file(path) == sensitivity_hash or b"SENSITIVITY VARIANT" in open(path, "rb").read():
                sys.exit(f"REFUSED: normal build contains sensitivity-variant code: {os.path.relpath(path, staging)}")


def _zip(staging, function, target):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for package in (function, "shared"):
            for name in sorted(os.listdir(os.path.join(staging, package))):
                if name.endswith(".py"):
                    info = zipfile.ZipInfo(f"{package}/{name}", date_time=(1980, 1, 1, 0, 0, 0))
                    info.external_attr = 0o644 << 16
                    info.compress_type = zipfile.ZIP_DEFLATED
                    archive.writestr(info, open(os.path.join(staging, package, name), "rb").read())
    data = buffer.getvalue()
    open(target, "wb").write(data)
    digest = hashlib.sha256(data).digest()
    return {"file": os.path.basename(target), "sha256": digest.hex(), "lambda_code_sha256": base64.b64encode(digest).decode()}


def cmd_build(args):
    variant = args.variant
    staging = _stage(variant)
    if variant == "normal":
        _guard_normal(staging)
    out = os.path.join(BUILD, variant)
    manifest = {"schema": "tla-build/1", "variant": variant,
                "retrieval_scope_sha256": sha256_file(os.path.join(staging, "shared", "retrieval_scope.py")),
                "source_retrieval_scope_sha256": sha256_file(os.path.join(APP, "shared", "retrieval_scope.py")),
                "packages": {fn: _zip(staging, fn, os.path.join(out, f"{fn}.zip")) for fn in ("query", "ingestion")}}
    json.dump(manifest, open(os.path.join(out, "manifest.json"), "w"), indent=2)
    for fn, package in manifest["packages"].items():
        print(f"built {variant}/{fn}.zip sha256 {package['sha256']}")
    if variant == "sensitivity":
        print("NOTE: sensitivity build — the primary tenant constraint is REMOVED. Deploy only via sensitivity-run.sh.")
    return 0


# ── deploy ──────────────────────────────────────────────────────────────────────────────────────────────────────────
_TRANSIENT_BUCKET_ERRORS = ("NoSuchBucket", "OperationAborted")


def _retry_transient(call, attempts=12, delay=5, sleep=time.sleep):
    """S3 is briefly inconsistent when a bucket name is re-created soon after deletion (found by the E4 fresh-copy run:
    create succeeded, then PutPublicAccessBlock returned NoSuchBucket). Retry only those transient errors, bounded."""
    for attempt in range(attempts):
        try:
            return call()
        except Exception as error:  # noqa: BLE001
            if attempt == attempts - 1 or not any(code in f"{type(error).__name__} {error}" for code in _TRANSIENT_BUCKET_ERRORS):
                raise
            sleep(delay)


def _ensure_artifact_bucket(s3, bucket, variant, sleep=time.sleep):
    try:
        s3.head_bucket(Bucket=bucket)
    except Exception:  # noqa: BLE001
        def create():
            try:
                s3.create_bucket(Bucket=bucket)
            except Exception as error:  # noqa: BLE001
                if "BucketAlreadyOwnedByYou" not in f"{type(error).__name__} {error}":
                    raise
        _retry_transient(create, sleep=sleep)
    _retry_transient(lambda: s3.put_public_access_block(Bucket=bucket, PublicAccessBlockConfiguration={
        "BlockPublicAcls": True, "IgnorePublicAcls": True, "BlockPublicPolicy": True, "RestrictPublicBuckets": True}), sleep=sleep)
    _retry_transient(lambda: s3.put_bucket_policy(Bucket=bucket, Policy=json.dumps({"Version": "2012-10-17", "Statement": [{
        "Sid": "DenyInsecureTransport", "Effect": "Deny", "Principal": "*", "Action": "s3:*",
        "Resource": [f"arn:aws:s3:::{bucket}", f"arn:aws:s3:::{bucket}/*"],
        "Condition": {"Bool": {"aws:SecureTransport": "false"}}}]})), sleep=sleep)
    _retry_transient(lambda: s3.put_bucket_tagging(Bucket=bucket, Tagging={"TagSet": tags(variant)}), sleep=sleep)


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
        sys.exit(f"REFUSED: no build for '{variant}'. Run scripts/build.sh {variant} first.")
    manifest = json.load(open(manifest_path))
    if manifest["variant"] != variant:
        sys.exit("REFUSED: build manifest variant mismatch")
    if variant == "sensitivity" and os.environ.get("TLA_SENSITIVITY_RUN") != "1":
        sys.exit("REFUSED: the sensitivity variant is deployed only by scripts/sensitivity-run.sh")
    sess = session(config)
    account = account_guard(config, sess)
    n = names(variant, account)
    s3, cfn = sess.client("s3"), sess.client("cloudformation")
    _ensure_artifact_bucket(s3, n["artifact_bucket"], variant)
    keys = {}
    for fn, package in manifest["packages"].items():
        keys[fn] = f"functions/{package['sha256']}/{fn}.zip"
        s3.upload_file(os.path.join(BUILD, variant, package["file"]), n["artifact_bucket"], keys[fn])
    parameters = [{"ParameterKey": k, "ParameterValue": v} for k, v in {
        "NamePrefix": n["prefix"], "Variant": variant, "ArtifactBucket": n["artifact_bucket"],
        "QueryCodeKey": keys["query"], "IngestionCodeKey": keys["ingestion"], "RolePath": config["TLA_ROLE_PATH"],
        "PermissionsBoundaryArn": config["TLA_PERMISSIONS_BOUNDARY_ARN"]}.items()]
    body = open(TEMPLATE, encoding="utf-8").read()
    common = {"StackName": n["stack"], "TemplateBody": body, "Parameters": parameters,
              "Capabilities": ["CAPABILITY_NAMED_IAM"], "Tags": tags(variant)}
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
    outputs = {o["OutputKey"]: o["OutputValue"] for o in stack.get("Outputs", [])}
    print(f"deployed {n['stack']} ({stack['StackStatus']}) in {int(time.time() - started)} s")
    print(f"  API endpoint   {outputs['ApiEndpoint']}")
    print(f"  resources      {len(cfn.describe_stack_resources(StackName=n['stack'])['StackResources'])}")
    return 0


# ── cleanup ─────────────────────────────────────────────────────────────────────────────────────────────────────────
def _empty_bucket(s3, bucket):
    removed = 0
    try:
        for page in s3.get_paginator("list_objects_v2").paginate(Bucket=bucket):
            keys = [{"Key": o["Key"]} for o in page.get("Contents", [])]
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
    stack_id = current["StackId"]
    for attempt in range(2):
        cfn.delete_stack(StackName=stack_id, **({} if attempt == 0 else {"RetainResources": retain}))
        final = _wait_stack(cfn, stack_id)
        if final["StackStatus"] == "DELETE_COMPLETE":
            return "DELETE_COMPLETE" + (" (retained never-created roles)" if attempt else "")
        # Documented rollback limitation: a role that was never created can block deletion. Retain it only if IAM
        # confirms it does not exist; anything else is reported, never hidden.
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


def cmd_cleanup(args):
    config = load_config()
    sess = session(config)
    account = account_guard(config, sess)
    s3, cfn = sess.client("s3"), sess.client("cloudformation")
    variants = VARIANTS[::-1] if args.variant == "all" else (args.variant,)   # sensitivity first
    failed = False
    for variant in variants:
        n = names(variant, account)
        try:
            outputs = {o["OutputKey"]: o["OutputValue"] for o in cfn.describe_stacks(StackName=n["stack"])["Stacks"][0].get("Outputs", [])}
        except Exception:  # noqa: BLE001
            outputs = {}
        document_bucket = outputs.get("DocumentBucket", f"{n['prefix']}-docs-{account}")
        print(f"[{variant}] document bucket objects removed: {_empty_bucket(s3, document_bucket)}")
        result = _delete_stack(sess, n["stack"])
        print(f"[{variant}] stack {n['stack']}: {result}")
        failed |= result.startswith("DELETE_FAILED")
        removed = _empty_bucket(s3, n["artifact_bucket"])
        try:
            s3.delete_bucket(Bucket=n["artifact_bucket"])
            print(f"[{variant}] artifact bucket {n['artifact_bucket']}: deleted ({removed} objects)")
        except Exception as error:  # noqa: BLE001
            print(f"[{variant}] artifact bucket {n['artifact_bucket']}: " + ("not present" if "NoSuchBucket" in str(error) else f"ERROR {error}"))
            failed |= "NoSuchBucket" not in str(error)
    print("cleanup: " + ("INCOMPLETE — see above; then run verify-cleanup" if failed else "done — now run: python3 -m harness verify-cleanup"))
    return 1 if failed else 0


def cmd_outputs(args):
    config = load_config()
    sess = session(config)
    account = sess.client("sts").get_caller_identity()["Account"]
    stack = sess.client("cloudformation").describe_stacks(StackName=names(args.variant, account)["stack"])["Stacks"][0]
    print(json.dumps({o["OutputKey"]: o["OutputValue"] for o in stack.get("Outputs", [])}, indent=2))
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("preflight")
    p.add_argument("--acknowledge-model-logging", action="store_true")
    p.set_defaults(func=cmd_preflight)
    for name, func in (("build", cmd_build), ("deploy", cmd_deploy), ("outputs", cmd_outputs)):
        p = sub.add_parser(name)
        p.add_argument("variant", choices=VARIANTS)
        p.set_defaults(func=func)
    p = sub.add_parser("cleanup")
    p.add_argument("--variant", choices=VARIANTS + ("all",), default="all")
    p.set_defaults(func=cmd_cleanup)
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
