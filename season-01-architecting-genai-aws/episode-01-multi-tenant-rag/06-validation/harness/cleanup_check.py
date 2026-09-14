"""TST-OPS-012 — verify cleanup with AUTHORITATIVE service lookups.

The resource tag index is eventually consistent: a deleted resource can still appear in a tag search for a while.
Every tagged ARN is therefore confirmed with its owning service before it counts as remaining. Durable account-level
foundation resources (for example a deployment role) are not part of this lab and are not reported.
"""
from harness.common import tla_ops


def _confirm(session, arn):
    """True if the owning service says the resource still exists."""
    service = arn.split(":")[2]
    try:
        if service == "cognito-idp":
            session.client("cognito-idp").describe_user_pool(UserPoolId=arn.rsplit("/", 1)[1])
        elif service == "lambda":
            session.client("lambda").get_function(FunctionName=arn.split(":function:")[1].split(":")[0])
        elif service == "dynamodb":
            session.client("dynamodb").describe_table(TableName=arn.split(":table/")[1].split("/")[0])
        elif service == "s3":
            session.client("s3").head_bucket(Bucket=arn.split(":::")[1].split("/")[0])
        elif service == "apigateway":
            session.client("apigatewayv2").get_api(ApiId=arn.split("/apis/")[1].split("/")[0])
        elif service == "logs":
            name = arn.split(":log-group:")[1].rstrip(":*")
            groups = session.client("logs").describe_log_groups(logGroupNamePrefix=name)["logGroups"]
            return any(g["logGroupName"] == name for g in groups)
        elif service == "bedrock":
            session.client("bedrock-agent").get_knowledge_base(knowledgeBaseId=arn.rsplit("/", 1)[1])
        elif service == "s3vectors":
            session.client("s3vectors").get_vector_bucket(vectorBucketArn=arn.split("/index/")[0])
        elif service == "cloudformation":
            status = session.client("cloudformation").describe_stacks(StackName=arn)["Stacks"][0]["StackStatus"]
            return status != "DELETE_COMPLETE"
        else:
            return True  # unknown type: count as remaining (fail safe)
        return True
    except Exception as error:  # noqa: BLE001
        text = f"{type(error).__name__} {error}"
        if any(s in text for s in ("NotFound", "NoSuch", "does not exist", "404", "ResourceNotFound")):
            return False
        return True


def verify(target_session, account, variants):
    session = target_session
    prefixes = [tla_ops.names(v, account)["prefix"] for v in variants]
    found = {}

    def starts(name):
        return any((name or "").startswith(p) for p in prefixes)

    cfn = session.client("cloudformation")
    found["stacks"] = [s["StackName"] for page in cfn.get_paginator("list_stacks").paginate() for s in page["StackSummaries"]
                       if starts(s["StackName"]) and s["StackStatus"] != "DELETE_COMPLETE"]
    found["knowledge_bases"] = [k["name"] for k in session.client("bedrock-agent").list_knowledge_bases()["knowledgeBaseSummaries"] if starts(k["name"])]
    found["vector_buckets"] = [b["vectorBucketName"] for b in session.client("s3vectors").list_vector_buckets()["vectorBuckets"] if starts(b["vectorBucketName"])]
    found["s3_buckets"] = [b["Name"] for b in session.client("s3").list_buckets()["Buckets"] if starts(b["Name"])]
    found["user_pools"] = [p["Name"] for p in session.client("cognito-idp").list_user_pools(MaxResults=60)["UserPools"] if starts(p["Name"])]
    found["functions"] = [f["FunctionName"] for page in session.client("lambda").get_paginator("list_functions").paginate()
                          for f in page["Functions"] if starts(f["FunctionName"])]
    found["tables"] = [t for t in session.client("dynamodb").list_tables()["TableNames"] if starts(t)]
    found["http_apis"] = [a["Name"] for a in session.client("apigatewayv2").get_apis()["Items"] if starts(a["Name"])]
    logs = session.client("logs")
    found["log_groups"] = [g["logGroupName"] for p in prefixes for prefix in (f"/aws/lambda/{p}", f"/tla/{p}")
                           for g in logs.describe_log_groups(logGroupNamePrefix=prefix)["logGroups"]]
    found["iam_roles"] = [r["RoleName"] for page in session.client("iam").get_paginator("list_roles").paginate()
                          for r in page["Roles"] if starts(r["RoleName"])]
    tagging = session.client("resourcegroupstaggingapi")
    tagged, stale = [], []
    for variant in variants:
        for page in tagging.get_paginator("get_resources").paginate(TagFilters=[
                {"Key": "Course", "Values": ["ThinkLikeAnArchitect"]}, {"Key": "Episode", "Values": ["01"]},
                {"Key": "Variant", "Values": [variant]}, {"Key": "Purpose", "Values": ["education"]}]):
            for mapping in page["ResourceTagMappingList"]:
                (tagged if _confirm(session, mapping["ResourceARN"]) else stale).append(mapping["ResourceARN"])
    found["tagged_resources_confirmed_by_owning_service"] = tagged
    clean = not any(found.values())
    return clean, found, stale
