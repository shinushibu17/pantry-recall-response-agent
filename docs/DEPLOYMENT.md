# AWS deployment

[Public demo](https://d1vhm9p26zmdc7.cloudfront.net) ?
[Architecture](submission/architecture.png) ? [Recorded checks](submission/EVIDENCE.md)

## Resources

Stack `pantry-recall-demo` runs in `us-east-1`.

| Resource | Purpose |
| --- | --- |
| EC2 t3.small / Amazon Linux 2023 | One Python application process |
| CloudFront distribution and VPC origin | Public HTTPS; uncached visitor responses |
| Encrypted 16 GB root EBS volume | OS and application |
| Encrypted 8 GB gp3 data volume | SQLite state; retained on stack deletion |
| Instance role | Nova Pro invocation (Nova Lite retained for rollback), release-prefix S3 reads and Systems Manager |
| Private, versioned S3 bucket | Application release archives; separate from the stack |

CloudFront reaches the private origin. The instance has outbound connectivity
for package installation and AWS calls; its security group accepts port 8080
from CloudFront's managed prefix list and provides no SSH entry point. Bootstrap
installs pinned dependencies and mounts an existing data filesystem without
formatting it. The runtime uses the instance role, not personal credentials.

## Deploy

Configure AWS credentials with permissions for the resources above. Planning
writes local files only; `deploy` creates billable AWS resources.

```sh
uv run --frozen python tools/deploy_aws.py plan
uv run --frozen python tools/deploy_aws.py deploy
uv run --frozen python tools/deploy_aws.py status
```

After the server stack reaches CREATE_COMPLETE, run `advance` to add the VPC
origin. Wait for UPDATE_COMPLETE and the origin's Deployed status, then run it
again to add CloudFront. Inspect stack events and service logs if a stage fails.

```sh
uv run --frozen python tools/deploy_aws.py advance
uv run --frozen python tools/deploy_aws.py configure
```

Run `configure` only once the distribution URL exists. It sets the service's
HTTPS origin and Bedrock model through Systems Manager and restarts the app. Deployment metadata
and command IDs stay in ignored `outputs/deployment/`.

## Verify and update

Verify HTTPS `/health`, a complete agent investigation and persistent receipts.
The boundary check below restarts the service; the live workflow check consumes
four agent starts. Use new output directories to preserve earlier observations.

```sh
uv run --frozen python tools/verify_deployment.py --no-agent --restart-service --output outputs/deployment/new-boundary-check
uv run --frozen python -m tools.verify_investigation --url https://d1vhm9p26zmdc7.cloudfront.net --output outputs/deployment/new-workflow-check
```

Publish application changes while preserving the data volume:

```sh
uv run --frozen python tools/deploy_aws.py update-code
```

The default model is `amazon.nova-pro-v1:0`. The instance policy explicitly
permits that model and Nova Lite; no wildcard model access is granted. Updating
code alone does not change an existing IAM policy. For an older stack, review an
IAM-only CloudFormation change set before selecting Pro. To select the fallback:

```sh
uv run --frozen python tools/deploy_aws.py configure --model-id amazon.nova-lite-v1:0
```

Use Systems Manager for `systemctl status pantry-recall` and
`journalctl -u pantry-recall`. Check command completion. The updater stops the
service before replacing application files and syncing dependencies; old files
are not automatically pruned.

## Runtime limits and persistence

Anonymous cookies isolate synthetic visitor replays. Sessions last seven days;
allocation is bounded at 200 replays and 150 events per replay. The shared quota
is 20 agent starts per UTC day with one concurrent run. Restarting a demo does
not reset it. Accepted evidence survives inference failures. Only synthetic data
belongs in the demo; reviewer names and confirmations are user assertions.

The registry is `/var/lib/pantry/pantry.sqlite3`; visitor databases are in its
`visitors/` directory on retained EBS. Service restarts preserve events and
receipts. Multiple application replicas, scheduled backups and failover are not
implemented. See [agent behavior](AGENT-ROLE.md) for follow-up handling.

To recover a deleted stack, pass `--data-volume vol-...` to `deploy`. The script
requires a detached, encrypted Pantry-tagged volume and uses its availability
zone. An explicitly supplied recovery disk stays outside the new stack lifecycle.

## Teardown

Deleting the stack removes the instance, CloudFront resources and runtime role.
The data volume and versioned artifact bucket remain intentionally. Export a
consistent SQLite backup before deleting either. Removing all bucket versions
and the retained volume is a separate operation. Compute, storage, IPv4,
CloudFront, S3 and Bedrock can incur charges; the agent quota is not a billing cap.
