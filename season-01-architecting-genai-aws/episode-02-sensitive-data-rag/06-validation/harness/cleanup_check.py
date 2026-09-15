"""Verify cleanup with authoritative service lookups (TST-OPS cleanup evidence).

Lists every resource type the deployment creates, by the episode's name prefixes, and confirms any tagged resource with
its owning service (the tag index is eventually consistent). The shared account foundation is not part of the lab and
is not reported.
"""
from harness.common import tla_ops


def _confirm(session, arn):
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
            return session.client("cloudformation").describe_stacks(StackName=arn)["Stacks"][0]["StackStatus"] != "DELETE_COMPLETE"
        else:
            return True
        return True
    except Exception as error:  # noqa: BLE001
        text = f"{type(error).__name__} {error}"
        return not any(s in text for s in ("NotFound", "NoSuch", "does not exist", "404", "ResourceNotFound"))


def verify(session, account, variants):
    prefixes = [tla_ops.names(v, account)["prefix"] for v in variants]

    def starts(name):
        return any((name or "").startswith(p) for p in prefixes)

    found = {}
    cfn = session.client("cloudformation")
    found["stacks"] = [s["StackName"] for page in cfn.get_paginator("list_stacks").paginate() for s in page["StackSummaries"]
                       if starts(s["StackName"]) and s["StackStatus"] != "DELETE_COMPLETE"]
    agent = session.client("bedrock-agent")
    kbs, kwargs = [], {"maxResults": 100}
    while True:
        page = agent.list_knowledge_bases(**kwargs)
        kbs += [k["name"] for k in page["knowledgeBaseSummaries"] if starts(k["name"])]
        if not page.get("nextToken"):
            break
        kwargs["nextToken"] = page["nextToken"]
    found["knowledge_bases"] = kbs
    found["vector_buckets"] = [b["vectorBucketName"] for b in session.client("s3vectors").list_vector_buckets()["vectorBuckets"]
                               if starts(b["vectorBucketName"])]
    found["s3_buckets"] = [b["Name"] for b in session.client("s3").list_buckets()["Buckets"] if starts(b["Name"])]
    pools, kwargs = [], {"MaxResults": 60}
    while True:
        page = session.client("cognito-idp").list_user_pools(**kwargs)
        pools += [p["Name"] for p in page["UserPools"] if starts(p["Name"])]
        if not page.get("NextToken"):
            break
        kwargs["NextToken"] = page["NextToken"]
    found["user_pools"] = pools
    found["functions"] = [f["FunctionName"] for page in session.client("lambda").get_paginator("list_functions").paginate()
                          for f in page["Functions"] if starts(f["FunctionName"])]
    found["tables"] = [t for page in session.client("dynamodb").get_paginator("list_tables").paginate()
                       for t in page["TableNames"] if starts(t)]
    found["http_apis"] = [a["Name"] for a in session.client("apigatewayv2").get_apis()["Items"] if starts(a["Name"])]
    logs = session.client("logs")
    found["log_groups"] = [g["logGroupName"] for p in prefixes for prefix in (f"/aws/lambda/{p}", f"/tla/{p}")
                           for g in logs.describe_log_groups(logGroupNamePrefix=prefix)["logGroups"]]
    found["iam_roles"] = [r["RoleName"] for page in session.client("iam").get_paginator("list_roles").paginate()
                          for r in page["Roles"] if starts(r["RoleName"])]
    tagged, stale = [], []
    for page in session.client("resourcegroupstaggingapi").get_paginator("get_resources").paginate(TagFilters=[
            {"Key": "Course", "Values": ["ThinkLikeAnArchitect"]}, {"Key": "Episode", "Values": ["02"]}]):
        for mapping in page["ResourceTagMappingList"]:
            arn = mapping["ResourceARN"]
            tag_prefix = {t["Key"]: t["Value"] for t in mapping.get("Tags", [])}
            if not any(p in arn for p in prefixes) and tag_prefix.get("Variant") not in (
                    {"normal"} if variants == ["normal"] else {"normal", "sensitivity"} if "normal" in variants else {"sensitivity"}):
                continue
            (tagged if _confirm(session, arn) else stale).append(arn)
    found["tagged_resources_confirmed_by_owning_service"] = tagged
    return not any(found.values()), found, stale
