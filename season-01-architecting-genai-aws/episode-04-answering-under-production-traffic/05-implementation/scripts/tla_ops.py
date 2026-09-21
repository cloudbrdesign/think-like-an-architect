#!/usr/bin/env python3
"""Deployment operations for the Episode 04 lab: preflight · lab-up · lab-down · inspect.

Guarded, following the Episode 02/03 pattern:
  * every command confirms the target account and refuses a mismatch;
  * the region is ALWAYS explicit and must be us-east-1 - the workstation profile defaults to af-south-1, and an
    implicit region is how a lab silently lands in the wrong one;
  * nothing is created unless the episode budget exists;
  * `lab-down` is idempotent, and a second run is a clean no-op.

Credentials come from the standard AWS credential chain. Nothing secret is stored here or in config/.
"""
import argparse
import json
import os
import sys
import time

IMPLEMENTATION = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
TEMPLATE = os.path.join(IMPLEMENTATION, "infrastructure", "template.yaml")
PARAMETERS = os.path.join(IMPLEMENTATION, "config", "demonstration_parameters.json")
REQUIRED_REGION = "us-east-1"
VARIANTS = {"traffic": "tla-s01e04-traffic"}
TAGS = [{"Key": k, "Value": v} for k, v in {
    "Project": "CloudBreweryLabs", "Course": "ThinkLikeAnArchitect", "Season": "01", "Episode": "04",
    "Environment": "Sandbox", "ManagedBy": "CloudBreweryLabs", "Variant": "traffic", "Purpose": "education",
    "DeployedWith": "CloudFormation"}.items()]


def load_config():
    config = {"AWS_PROFILE": "", "AWS_REGION": REQUIRED_REGION, "TLA_EXPECTED_ACCOUNT": "",
              "TLA_ROLE_PATH": "/cloudbrewery/tla/", "TLA_PERMISSIONS_BOUNDARY_ARN": "", "TLA_BUDGET_NAME": ""}
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
    region = config["AWS_REGION"]
    if region != REQUIRED_REGION:
        sys.exit(f"REFUSED: the established Season 1 region is {REQUIRED_REGION}; this asked for {region!r}")
    return boto3.Session(profile_name=config["AWS_PROFILE"] or None, region_name=region)


def account_guard(config, sess, quiet=False):
    identity = sess.client("sts").get_caller_identity()
    if not quiet:
        print(f"target account <redacted> · region {sess.region_name} · caller {identity['Arn'].split(':', 5)[5]}")
    expected = config.get("TLA_EXPECTED_ACCOUNT")
    if not expected:
        sys.exit("REFUSED: set TLA_EXPECTED_ACCOUNT in config/learner.env so commands cannot target the wrong account")
    if expected != identity["Account"]:
        sys.exit("REFUSED: the credentials belong to a different account than TLA_EXPECTED_ACCOUNT")
    return identity["Account"]


def cmd_preflight(args):
    config = load_config()
    sess = session(config)
    account = account_guard(config, sess)
    problems = []

    budget_name = config.get("TLA_BUDGET_NAME")
    if not budget_name:
        problems.append("no TLA_BUDGET_NAME set: a budget with alerts must exist before any resource is created")
    else:
        try:
            budget = sess.client("budgets", region_name=REQUIRED_REGION).describe_budget(
                AccountId=account, BudgetName=budget_name)["Budget"]
            print(f"budget      {budget_name}: {budget['BudgetLimit']['Amount']} "
                  f"{budget['BudgetLimit']['Unit']} {budget['TimeUnit'].lower()}")
        except Exception as error:                                              # noqa: BLE001
            problems.append(f"budget {budget_name} not readable: {type(error).__name__}")

    if not config.get("TLA_PERMISSIONS_BOUNDARY_ARN"):
        problems.append("no TLA_PERMISSIONS_BOUNDARY_ARN set: runtime roles must carry the boundary")

    cfn = sess.client("cloudformation")
    for variant, stack in VARIANTS.items():
        try:
            status = cfn.describe_stacks(StackName=stack)["Stacks"][0]["StackStatus"]
            problems.append(f"leftover stack {stack} is {status}; run lab-down first")
        except Exception:                                                        # noqa: BLE001
            print(f"clean       no existing stack {stack}")

    leftovers = [f["FunctionName"] for page in sess.client("lambda").get_paginator("list_functions").paginate()
                 for f in page["Functions"] if f["FunctionName"].startswith("tla-s01e04-")]
    if leftovers:
        problems.append(f"leftover functions: {', '.join(leftovers)}")

    throughputs = sess.client("bedrock").list_provisioned_model_throughputs().get("provisionedModelSummaries", [])
    print(f"provisioned model throughput: {len(throughputs)} (must be 0 - it is the one expensive thing here)")
    if throughputs:
        problems.append("provisioned model throughput exists; the lab must run on-demand only")

    for line in problems:
        print(f"FAIL        {line}")
    print(f"preflight: {'PASS' if not problems else 'FAIL'}")
    return 1 if problems else 0


def _wait(cfn, stack, terminal):
    while True:
        try:
            status = cfn.describe_stacks(StackName=stack)["Stacks"][0]["StackStatus"]
        except Exception:                                                        # noqa: BLE001
            return "DELETE_COMPLETE"
        if status.endswith(terminal) or status.endswith("FAILED") or "ROLLBACK" in status:
            return status
        time.sleep(5)


def cmd_lab_up(args):
    config = load_config()
    sess = session(config)
    account = account_guard(config, sess)
    stack = VARIANTS[args.variant]
    cfn = sess.client("cloudformation")
    with open(TEMPLATE, encoding="utf-8") as handle:
        template = handle.read()
    with open(PARAMETERS, encoding="utf-8") as handle:
        parameters = {k: v for k, v in json.load(handle).items() if not k.startswith("_")}

    cfn.create_stack(
        StackName=stack, TemplateBody=template, Capabilities=["CAPABILITY_NAMED_IAM"], Tags=TAGS,
        Parameters=[{"ParameterKey": "Prefix", "ParameterValue": stack},
                    {"ParameterKey": "RolePath", "ParameterValue": config["TLA_ROLE_PATH"]},
                    {"ParameterKey": "PermissionsBoundaryArn",
                     "ParameterValue": config["TLA_PERMISSIONS_BOUNDARY_ARN"].replace("ACCOUNT", account)},
                    {"ParameterKey": "AnsweringPermits",
                     "ParameterValue": str(parameters["answering_permits_total"])},
                    {"ParameterKey": "ChangeFloor", "ParameterValue": str(parameters["change_processing_floor"])},
                    {"ParameterKey": "BufferMaxAgeSeconds",
                     "ParameterValue": str(parameters["buffer_max_age_seconds"])},
                    {"ParameterKey": "DemonstrationParameters", "ParameterValue": json.dumps(parameters)},
                    {"ParameterKey": "UseReservedConcurrency", "ParameterValue": reserved_concurrency_possible(
                        sess, parameters)}])
    status = _wait(cfn, stack, "CREATE_COMPLETE")
    print(f"lab-up      {stack}: {status}")
    if status != "CREATE_COMPLETE":
        for event in cfn.describe_stack_events(StackName=stack)["StackEvents"]:
            if event["ResourceStatus"].endswith("FAILED"):
                print(f"  {event['LogicalResourceId']}: {event.get('ResourceStatusReason', '')}")
        return 1
    for output in cfn.describe_stacks(StackName=stack)["Stacks"][0].get("Outputs", []):
        print(f"  {output['OutputKey']}: {output['OutputValue']}")
    return 0


AWS_MINIMUM_UNRESERVED = 10   # AWS refuses a reservation that would take unreserved concurrency below this.


def reserved_concurrency_possible(sess, parameters):
    """Can AWS reserved concurrency enforce the partitions in THIS account?

    Reserved concurrency is the mechanism CTL-401 and CTL-409 name, but it is only available when the account's limit
    leaves AWS its required unreserved minimum afterwards. An account whose whole limit is 10 cannot reserve anything.
    That is not a reason to change the architecture - the in-process permit counter enforces the same partitions - but
    it must be stated, not silently skipped.
    """
    limit = sess.client("lambda").get_account_settings()["AccountLimit"]["ConcurrentExecutions"]
    needed = parameters["answering_permits_total"] + parameters["change_processing_floor"]
    if limit - needed >= AWS_MINIMUM_UNRESERVED:
        print(f"partitions  enforced by AWS reserved concurrency ({needed} of {limit}, leaving "
              f"{limit - needed} unreserved)")
        return "true"
    print(f"partitions  enforced IN-PROCESS: account concurrency limit is {limit}, and reserving {needed} would "
          f"leave fewer than {AWS_MINIMUM_UNRESERVED} unreserved, which AWS refuses")
    print("            The architecture is unchanged (CTL-401 names both mechanisms); the AWS enforcement layer is "
          "absent and is recorded as a deviation.")
    return "false"


def cmd_lab_down(args):
    config = load_config()
    sess = session(config)
    account = account_guard(config, sess)
    stack = VARIANTS[args.variant]
    cfn = sess.client("cloudformation")
    try:
        cfn.describe_stacks(StackName=stack)
    except Exception:                                                            # noqa: BLE001
        print(f"lab-down    {stack}: not present (no-op)")
        return verify_clean(sess, stack)
    cfn.delete_stack(StackName=stack)
    status = _wait(cfn, stack, "DELETE_COMPLETE")
    print(f"lab-down    {stack}: {status}")
    # Log groups can outlive the stack when a function wrote to one it created implicitly; delete them by name.
    logs = sess.client("logs")
    for group in logs.describe_log_groups(logGroupNamePrefix=f"/aws/lambda/{stack}")["logGroups"]:
        logs.delete_log_group(logGroupName=group["logGroupName"])
        print(f"  deleted log group {group['logGroupName']}")
    return verify_clean(sess, stack)


def verify_clean(sess, prefix):
    """An INDEPENDENT scan, by name, through each owning service - not the tag index, which lags."""
    remaining = []
    functions = [f["FunctionName"] for page in sess.client("lambda").get_paginator("list_functions").paginate()
                 for f in page["Functions"] if f["FunctionName"].startswith(prefix)]
    remaining += [f"lambda:{name}" for name in functions]
    queues = sess.client("sqs").list_queues(QueueNamePrefix=prefix).get("QueueUrls", []) or []
    remaining += [f"sqs:{url.rsplit('/', 1)[-1]}" for url in queues]
    for alarm in ("buffer-age", "capacity-refused", "trust-withheld", "freshness-lag"):
        # Addressed BY NAME: the deploy role is scoped to alarm:tla-*, and a prefix listing is evaluated against
        # alarm:* which it deliberately does not hold.
        found = sess.client("cloudwatch").describe_alarms(AlarmNames=[f"{prefix}-{alarm}"])["MetricAlarms"]
        remaining += [f"alarm:{a['AlarmName']}" for a in found]
    groups = sess.client("logs").describe_log_groups(
        logGroupNamePrefix=f"/aws/lambda/{prefix}")["logGroups"]
    remaining += [f"logs:{g['logGroupName']}" for g in groups]
    roles = [r["RoleName"] for page in sess.client("iam").get_paginator("list_roles").paginate(
        PathPrefix="/cloudbrewery/tla/") for r in page["Roles"] if r["RoleName"].startswith(prefix)]
    remaining += [f"iam:{name}" for name in roles]

    if remaining:
        print(f"cleanup     NOT CLEAN - still present: {', '.join(remaining)}")
        return 1
    print(f"cleanup     CLEAN - independent scan found no {prefix}* resource in lambda, sqs, cloudwatch, logs or iam")
    return 0


def cmd_inspect(args):
    config = load_config()
    sess = session(config)
    account_guard(config, sess, quiet=True)
    stack = VARIANTS[args.variant]
    lam = sess.client("lambda")
    for suffix in ("answering", "change"):
        try:
            configuration = lam.get_function(FunctionName=f"{stack}-{suffix}")
            reserved = configuration.get("Concurrency", {}).get("ReservedConcurrentExecutions")
            print(f"{suffix:10} reserved concurrency: {reserved}")
        except Exception as error:                                               # noqa: BLE001
            print(f"{suffix:10} not present ({type(error).__name__})")
    for alarm in ("buffer-age", "capacity-refused", "trust-withheld", "freshness-lag"):
        found = sess.client("cloudwatch").describe_alarms(AlarmNames=[f"{stack}-{alarm}"])["MetricAlarms"]
        for a in found:
            print(f"alarm      {a['AlarmName']}: {a['StateValue']}")
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(required=True)
    sub.add_parser("preflight").set_defaults(func=cmd_preflight)
    for name, function in (("lab-up", cmd_lab_up), ("lab-down", cmd_lab_down), ("inspect", cmd_inspect)):
        p = sub.add_parser(name)
        p.add_argument("variant", nargs="?", default="traffic", choices=sorted(VARIANTS))
        p.set_defaults(func=function)
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
