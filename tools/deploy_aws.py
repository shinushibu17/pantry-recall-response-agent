"""Deploy the reviewer to AWS. State and secrets stay in ignored outputs/deployment.

One EC2 process preserves the existing SQLite transaction boundary on an encrypted,
retained EBS volume. CloudFront reaches the server through a VPC origin. No SSH.
"""

import argparse
import hashlib
import io
import json
from pathlib import Path
import tarfile

import boto3
from botocore.exceptions import ClientError

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "outputs/deployment"
STACK = "pantry-recall-demo"
RUNTIME_MODELS = ("amazon.nova-lite-v1:0", "amazon.nova-pro-v1:0")
DEFAULT_MODEL = "amazon.nova-pro-v1:0"


def template(bucket, key, subnet, vpc, zone, prefix, ami, data_volume=None):
    bootstrap = (ROOT / "deployment/bootstrap.sh").read_text().replace("__BUCKET__", bucket).replace("__KEY__", key)
    if data_volume:
        bootstrap = bootstrap.replace("${DataVolume}", data_volume)
    ref = lambda key: data_volume if key == "DataVolume" and data_volume else {"Ref": key}
    att = lambda key, attr: {"Fn::GetAtt": [key, attr]}
    resources = {
        "ServerRole": {"Type": "AWS::IAM::Role", "Properties": {
            "AssumeRolePolicyDocument": {"Version":"2012-10-17", "Statement":[{"Effect":"Allow","Principal":{"Service":"ec2.amazonaws.com"},"Action":"sts:AssumeRole"}]},
            "ManagedPolicyArns":["arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"],
            "Policies":[{"PolicyName":"PantryRuntime", "PolicyDocument":{"Version":"2012-10-17", "Statement":[
                {"Effect":"Allow","Action":["s3:GetObject"],"Resource":f"arn:aws:s3:::{bucket}/release/*"},
                {"Effect":"Allow","Action":["bedrock:InvokeModel"],"Resource":[f"arn:aws:bedrock:us-east-1::foundation-model/{model}" for model in RUNTIME_MODELS]},
                {"Effect":"Allow","Action":"cloudformation:SignalResource","Resource":{"Ref":"AWS::StackId"}}
            ]}}]}},
        "ServerProfile": {"Type":"AWS::IAM::InstanceProfile", "Properties":{"Roles":[ref("ServerRole")]}},
        "ServerSecurityGroup": {"Type":"AWS::EC2::SecurityGroup", "Properties":{
            "GroupDescription":"Pantry HTTP from CloudFront only; no SSH", "VpcId":vpc,
            "SecurityGroupIngress":[{"IpProtocol":"tcp","FromPort":8080,"ToPort":8080,"SourcePrefixListId":prefix}],
            "SecurityGroupEgress":[{"IpProtocol":"tcp","FromPort":443,"ToPort":443,"CidrIp":"0.0.0.0/0"},
                                    {"IpProtocol":"tcp","FromPort":80,"ToPort":80,"CidrIp":"0.0.0.0/0"}]}},
        "DataVolume": {"Type":"AWS::EC2::Volume", "DeletionPolicy":"Retain", "UpdateReplacePolicy":"Retain",
            "Properties":{"AvailabilityZone":zone,"Size":8,"VolumeType":"gp3","Encrypted":True,
                          "Tags":[{"Key":"Name","Value":"pantry-recall-persistent-data"}]}},
        "Server": {"Type":"AWS::EC2::Instance", "CreationPolicy":{"ResourceSignal":{"Timeout":"PT15M","Count":1}},
            "Properties":{"ImageId":ami,"InstanceType":"t3.small", "CreditSpecification":{"CPUCredits":"standard"}, "IamInstanceProfile":ref("ServerProfile"),
                "MetadataOptions":{"HttpTokens":"required","HttpPutResponseHopLimit":1},
                "NetworkInterfaces":[{"DeviceIndex":"0","SubnetId":subnet,"AssociatePublicIpAddress":True,"GroupSet":[ref("ServerSecurityGroup")]}],
                "BlockDeviceMappings":[{"DeviceName":"/dev/xvda","Ebs":{"VolumeSize":16,"VolumeType":"gp3","Encrypted":True,"DeleteOnTermination":True}}],
                "Tags":[{"Key":"Name","Value":"pantry-recall-demo"}],
                "UserData":{"Fn::Base64":{"Fn::Sub":bootstrap}}}},
        "AttachData": {"Type":"AWS::EC2::VolumeAttachment", "Properties":{"Device":"/dev/sdf","InstanceId":ref("Server"),"VolumeId":ref("DataVolume")}},
        "PrivateOrigin": {"Type":"AWS::CloudFront::VpcOrigin", "DependsOn":"Server", "Properties":{"VpcOriginEndpointConfig":{
            "Name":"pantry-recall-demo", "Arn":{"Fn::Sub":"arn:aws:ec2:${AWS::Region}:${AWS::AccountId}:instance/${Server}"},
            "HTTPPort":8080,"HTTPSPort":443,"OriginProtocolPolicy":"http-only","OriginSSLProtocols":["TLSv1.2"]}}},
        "Distribution": {"Type":"AWS::CloudFront::Distribution", "DependsOn":"PrivateOrigin", "Properties":{"DistributionConfig":{
            "Enabled":True, "Comment":"Pantry Recall public isolated synthetic demo", "PriceClass":"PriceClass_100", "HttpVersion":"http2", "IPV6Enabled":True,
            "Origins":[{"Id":"pantry","DomainName":att("Server","PrivateDnsName"),"VpcOriginConfig":{"VpcOriginId":att("PrivateOrigin","Id"),"OriginReadTimeout":30,"OriginKeepaliveTimeout":5}}],
            "DefaultCacheBehavior":{"TargetOriginId":"pantry","ViewerProtocolPolicy":"redirect-to-https",
                "AllowedMethods":["GET","HEAD","OPTIONS","PUT","PATCH","POST","DELETE"],"CachedMethods":["GET","HEAD"],
                "CachePolicyId":"4135ea2d-6df8-44a3-9df3-4b5a84be39ad", "OriginRequestPolicyId":"216adef6-5c7f-47e4-b989-5492eafa07d3", "Compress":True},
            "ViewerCertificate":{"CloudFrontDefaultCertificate":True},
            "CustomErrorResponses":[{"ErrorCode":code,"ErrorCachingMinTTL":0} for code in [400,403,404,500,502,503,504]]}}},
    }
    # Attach the persistent volume using the EC2 Volumes property, before cloud-init signals success.
    # A separate attachment depending on the signal-complete instance would deadlock bootstrap.
    del resources["AttachData"]
    resources["Server"]["Properties"]["Volumes"]=[{"Device":"/dev/sdf","VolumeId":ref("DataVolume")}]
    if data_volume:
        del resources["DataVolume"]
    return {"AWSTemplateFormatVersion":"2010-09-09", "Description":"Pantry Recall reviewer demo: private CloudFront origin, EC2, retained EBS and Bedrock",
            "Resources":resources, "Outputs":{"Url":{"Value":{"Fn::Sub":"https://${Distribution.DomainName}"}},
                "InstanceId":{"Value":ref("Server")},"DataVolumeId":{"Value":ref("DataVolume")},"DistributionId":{"Value":ref("Distribution")}}}


def bundle():
    raw = io.BytesIO()
    with tarfile.open(fileobj=raw, mode="w:gz") as archive:
        for path in [ROOT/"pyproject.toml", ROOT/"uv.lock", ROOT/"tools/acquire_fixture.py", *sorted((ROOT/"pantry_recall").rglob("*")), *sorted((ROOT/"fixtures/pearl_milling_2025").rglob("*"))]:
            if path.is_file() and "__pycache__" not in path.parts and path.suffix != ".pyc":
                archive.add(path, arcname=path.relative_to(ROOT).as_posix())
    return raw.getvalue()


def command(session, instance, commands):
    result = session.client("ssm").send_command(InstanceIds=[instance], DocumentName="AWS-RunShellScript", Parameters={"commands":commands})
    return result["Command"]["CommandId"]


def stage_template(body, edge_stage):
    """CloudFront association requires Deployed, beyond configuration-complete."""
    document = json.loads(body)
    if edge_stage < 2:
        document["Resources"].pop("Distribution")
        document["Outputs"].pop("Url")
        document["Outputs"].pop("DistributionId")
    if edge_stage < 1:
        document["Resources"].pop("PrivateOrigin")
    return json.dumps(document)


def plan(session, data_volume=None):
    account = session.client("sts").get_caller_identity()["Account"]
    bucket = f"pantry-recall-demo-{account}-us-east-1"
    data = bundle()
    key = "release/" + hashlib.sha256(data).hexdigest() + ".tar.gz"
    ec2 = session.client("ec2")
    subnets = ec2.describe_subnets(Filters=[{"Name":"default-for-az","Values":["true"]}])["Subnets"]
    if data_volume:
        volume = ec2.describe_volumes(VolumeIds=[data_volume])["Volumes"][0]
        if volume["State"] != "available" or not volume["Encrypted"] or volume["Attachments"]:
            raise ValueError("Recovery volume must be encrypted, available and detached")
        if {tag["Key"]:tag["Value"] for tag in volume.get("Tags", [])}.get("Name") != "pantry-recall-persistent-data":
            raise ValueError("Recovery volume is not a Pantry data volume")
        subnets = [subnet for subnet in subnets if subnet["AvailabilityZone"] == volume["AvailabilityZone"]]
    subnet = next(s for s in subnets if s["AvailabilityZoneId"] != "use1-az3" and s["AvailableIpAddressCount"] > 10)
    prefix = ec2.describe_managed_prefix_lists(Filters=[{"Name":"prefix-list-name","Values":["com.amazonaws.global.cloudfront.origin-facing"]}])["PrefixLists"][0]["PrefixListId"]
    ami = session.client("ssm").get_parameter(Name="/aws/service/ami-amazon-linux-latest/al2023-ami-kernel-default-x86_64")["Parameter"]["Value"]
    body = json.dumps(template(bucket,key,subnet["SubnetId"],subnet["VpcId"],subnet["AvailabilityZone"],prefix,ami,data_volume),indent=2)
    (OUTPUT/"template.json").write_text(body,encoding="utf-8")
    session.client("cloudformation").validate_template(TemplateBody=body)
    (OUTPUT/"plan.json").write_text(json.dumps({"status":"TEMPLATE_VALIDATED_NOT_DEPLOYED","stack":STACK,"region":"us-east-1",
        "instance_type":"t3.small","data_volume_gb":8,"root_volume_gb":16,"data_retained_on_stack_deletion":True,
        "runtime":"existing Python / SQLite / Strands / Bedrock", "access":"Public HTTPS; isolated anonymous demo sessions; no password or SSH",
        "model":DEFAULT_MODEL,"daily_agent_run_limit":20,"bundle_bytes":len(data)},indent=2))
    return bucket, key, data, body


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["plan","deploy","advance","status","configure","update-code"])
    parser.add_argument("--profile", default="pantry-recall")
    parser.add_argument("--model-id", choices=RUNTIME_MODELS, default=DEFAULT_MODEL, help="Model for configure; both supported models have bounded IAM access")
    parser.add_argument("--data-volume", help="Reattach an existing retained Pantry disk in its original availability zone")
    args = parser.parse_args()
    session = boto3.Session(profile_name=args.profile, region_name="us-east-1")
    cf, ec2, s3 = session.client("cloudformation"), session.client("ec2"), session.client("s3")
    OUTPUT.mkdir(parents=True, exist_ok=True)
    if args.action == "plan":
        plan(session,args.data_volume)
        print("Read-only AWS validation complete. Template and plan saved under outputs/deployment. No resources created.")
    elif args.action == "deploy":
        try:
            existing = cf.describe_stacks(StackName=STACK)["Stacks"][0]
        except ClientError as error:
            if "does not exist" not in error.response["Error"].get("Message", ""):
                raise
        else:
            raise RuntimeError(f"Stack already exists ({existing['StackStatus']}); use status or update-code. No secrets were changed.")
        bucket, key, data, body = plan(session,args.data_volume)
        try:
            s3.head_bucket(Bucket=bucket)
        except ClientError as error:
            if error.response["Error"]["Code"] not in ("404", "NoSuchBucket"):
                raise
            s3.create_bucket(Bucket=bucket)
        s3.put_public_access_block(Bucket=bucket,PublicAccessBlockConfiguration={key:True for key in ["BlockPublicAcls","IgnorePublicAcls","BlockPublicPolicy","RestrictPublicBuckets"]})
        s3.put_bucket_versioning(Bucket=bucket, VersioningConfiguration={"Status":"Enabled"})
        s3.put_bucket_encryption(Bucket=bucket,ServerSideEncryptionConfiguration={"Rules":[{"ApplyServerSideEncryptionByDefault":{"SSEAlgorithm":"AES256"}}]})
        s3.put_bucket_policy(Bucket=bucket, Policy=json.dumps({"Version":"2012-10-17","Statement":[{"Effect":"Deny","Principal":"*","Action":"s3:*","Resource":[f"arn:aws:s3:::{bucket}",f"arn:aws:s3:::{bucket}/*"],"Condition":{"Bool":{"aws:SecureTransport":"false"}}}]}))
        s3.put_object(Bucket=bucket,Key=key,Body=data)
        result = cf.create_stack(StackName=STACK,TemplateBody=stage_template(body,0),DisableRollback=True,Capabilities=["CAPABILITY_IAM"],Tags=[{"Key":"Project","Value":"PantryRecallHackathon"}])
        (OUTPUT/"deployment.json").write_text(json.dumps({"stack_id":result["StackId"],"bucket":bucket,"artifact_key":key,"region":"us-east-1","reused_data_volume":args.data_volume},indent=2))
        print("Server deployment started. After CREATE_COMPLETE, use advance to add the VPC origin, then advance again after it is Deployed to add HTTPS.")
    else:
        stack = cf.describe_stacks(StackName=STACK)["Stacks"][0]
        outputs = {o["OutputKey"]:o["OutputValue"] for o in stack.get("Outputs",[])}
        print(json.dumps({"status":stack["StackStatus"],**outputs},indent=2))
        if args.action == "advance":
            if stack["StackStatus"] not in ("CREATE_COMPLETE", "UPDATE_COMPLETE"):
                raise RuntimeError("Wait for the current stack operation to complete before advancing")
            current = {r["LogicalResourceId"]:r for r in cf.describe_stack_resources(StackName=STACK)["StackResources"]}
            if "Distribution" in current:
                print("All infrastructure stages are present; configure the service origin next.")
                return
            phase = 1
            if "PrivateOrigin" in current:
                origin = session.client("cloudfront").get_vpc_origin(Id=current["PrivateOrigin"]["PhysicalResourceId"])["VpcOrigin"]
                if origin["Status"] != "Deployed":
                    print("Waiting for VPC origin: " + origin["Status"])
                    return
                phase = 2
            body = (OUTPUT/"template.json").read_text(encoding="utf-8")
            cf.update_stack(StackName=STACK,TemplateBody=stage_template(body,phase),Capabilities=["CAPABILITY_IAM"])
            print("Started infrastructure stage:",phase)
        elif args.action == "status":
            failed = [e for e in cf.describe_stack_events(StackName=STACK)["StackEvents"] if e["ResourceStatus"].endswith("FAILED")]
            for event in failed[:4]:
                print(event["LogicalResourceId"],event.get("ResourceStatusReason",""))
        elif args.action == "configure":
            url = outputs["Url"]
            if not url.startswith("https://") or not url.endswith(".cloudfront.net"):
                raise ValueError("Unexpected deployment URL")
            cmd = command(session,outputs["InstanceId"],["set -eu",f"printf 'PANTRY_PUBLIC_URL={url}\\nAWS_EC2_METADATA_DISABLED=false\\nBEDROCK_MODEL_ID={args.model_id}\\n' > /etc/pantry-public.env","systemctl restart pantry-recall","systemctl is-active pantry-recall"])
            (OUTPUT/"live.json").write_text(json.dumps({**outputs,"configure_command_id":cmd},indent=2))
            print("Service configuration command:",cmd)
        elif args.action == "update-code":
            deployment = json.loads((OUTPUT/"deployment.json").read_text())
            data = bundle()
            key = "release/"+hashlib.sha256(data).hexdigest()+".tar.gz"
            s3.put_object(Bucket=deployment["bucket"],Key=key,Body=data)
            # Stop the single process before replacing files; the data volume is untouched.
            cmd = command(session,outputs["InstanceId"],["set -eu",f"aws s3 cp s3://{deployment['bucket']}/{key} /tmp/pantry-release.tar.gz",
                "systemctl stop pantry-recall", "tar -xzf /tmp/pantry-release.tar.gz -C /opt/pantry", "cd /opt/pantry",
                "/usr/local/bin/uv sync --frozen --no-dev --python /usr/bin/python3.12 --no-managed-python", "systemctl start pantry-recall", "systemctl is-active pantry-recall"])
            print("Code update command:",cmd)


if __name__ == "__main__":
    main()
