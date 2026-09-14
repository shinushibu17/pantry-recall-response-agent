# Reviewer UI deployment

Status: **live and verified** at [the public demo](https://d1vhm9p26zmdc7.cloudfront.net). No password is required.
The agent investigation update passed public verification September 13, 2026
at 18:31 UTC. Four briefings completed all eight comparisons and seven tool
types: initial investigation, evidence arrival, partial hold and completed hold.
The latter three started automatically. Thirteen HTTP/confirmation boundary
checks passed at 18:32 UTC, including persistence across a service restart.
Reports: `outputs/deployment/investigation-check-1/verification.json` and
`outputs/deployment/agent-role-boundary-check/verification.json`.
The local suite contains 112 passing tests, including initialization from the exact
release archive outside the source workspace.

The later citation-loop fix is deployed. The previously failing browser session
completed with eight comparisons, ten tool calls and six model calls. Four fresh
public workflow stages passed with exact stored evidence bindings; see
`outputs/deployment/citation-fix-check/verification.json`. Deployment completion
is recorded in `outputs/deployment/citation-fix-update.json`.

The earlier baseline verification at 02:16:57 UTC passed 15 checks. A real Strands/Bedrock run from the
EC2 instance role completed all eight comparisons, using five tool calls and four
model calls in 5.01 seconds. Synthetic evidence entry, visitor isolation, partial
and final holds, exact replay, and cross-origin rejection passed. The same
visitor's complete history and confirmation receipts survived a service restart
on the mounted data volume. A separate browser run also displayed COMPLETE with
eight comparisons and five tools. Source publication/acquisition dates and exact
spans were checked in the live UI.

Evidence: `outputs/deployment/verification.json`, `public-agent-run.json`,
`runtime-access-check.json`, and `live.json`. The stack is `pantry-recall-demo`;
CloudFormation reports UPDATE_COMPLETE and CloudFront reports Deployed.

Two startup failures were resolved before publication: an unavailable AWS CLI
package and an omitted runtime source-parser module. The failed attempts remain
in ignored deployment records. The first empty data disk was removed; the second
retained disk was reattached without formatting. CloudFront creation uses separate
server, VPC-origin and distribution stages. The hosted service explicitly enables
EC2 metadata credentials; the local CLI's metadata probing remains disabled by default.

## Deployed resources

One CloudFormation stack, `pantry-recall-demo`, in us-east-1:

| Resource | Purpose |
| --- | --- |
| EC2 t3.small, Amazon Linux 2023 | One Python process, existing SQLite workflow and Strands SDK; standard CPU credits |
| Encrypted 16 GB gp3 root volume | OS and application; removed with instance |
| Encrypted 8 GB gp3 data volume | Visitor replays, events, receipts, agent reports and shared usage registry; **retained** on stack deletion/replacement |
| Instance role/profile | Invoke only Nova Lite in us-east-1, read the release prefix in the artifact bucket, signal its own stack, Systems Manager maintenance |
| Security group | Port 8080 from CloudFront's managed prefix list; no SSH; HTTP/HTTPS egress for bootstrap and AWS calls |
| CloudFront VPC origin + distribution | Password-free public HTTPS demo; origin traffic through the VPC; visitor responses are not cached |

A private, encrypted, versioned S3 artifact bucket is created separately by the
deployment script. Public access is blocked and non-TLS access denied. It holds
only packaged application source and the Pearl fixture. The runtime role can read
that release prefix. Personal AWS credentials, reviewer passwords, `.env`, local
outputs, databases and recordings are never bundled or uploaded.

The instance uses a public subnet/address for outbound package installation and
AWS calls; its security group does not accept public client traffic. CloudFront
connects to its private DNS address using a VPC origin. An anonymous HttpOnly,
SameSite=Strict, Secure cookie selects each visitor's isolated synthetic replay.
There is no login. Only a hash of the random cookie is stored. Sessions last seven
days; allocation is bounded at 200 replays with a 150-event limit per replay.
The 20-agent-starts/day allowance and one-running-agent limit are shared across
visitors and persist across restarts. Restart demo cannot reset the usage budget.
The first start enables event-triggered briefings; they use the same allowance.
Pause stops future automatic starts. Restart demo pauses the previous replay's
follow-ups while keeping its audit. Control state, pending event cursors and
run context are migrated through additive SQLite tables; accepted evidence and
receipts remain saved if inference fails. See [agent behavior](AGENT-ROLE.md).
The actor typed in a form remains an assertion. Source HTML is served as inert
plain text, never executable content. Bedrock tools cannot call human-write
endpoints. Only synthetic demo data belongs in this public application.

Architecture follows AWS's [VPC origin guidance](https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/private-content-vpc-origins.html)
and [CloudFormation VPC origin resource](https://docs.aws.amazon.com/AWSCloudFormation/latest/TemplateReference/aws-resource-cloudfront-vpcorigin.html).
Bootstrap installs the pinned uv 0.11.8 installer from Astral and synchronizes the
existing lockfile with system Python 3.12. See [Python on AL2023](https://docs.aws.amazon.com/linux/al2023/ug/python.html).

## Approximate ongoing cost

Before credits/tax, using 730 hours per month:

| Item | Approximate cost |
| --- | --- |
| t3.small at $0.0208/hour | $15.18/month |
| One public IPv4 at $0.005/hour | $3.65/month |
| 24 GB gp3 at $0.08/GB-month | $1.92/month |
| Baseline | **About $21/month, or $0.70/day** |

This is an estimate, not a spending cap. Bedrock tokens, S3 requests/storage,
CloudFront requests and traffic are additional. The application limits agent
starts to 20 per UTC day and one concurrent run; that does not cap all AWS charges.
The retained 8 GB data disk continues costing roughly $0.64/month after stack
deletion, as does the artifact bucket until explicitly removed.

Sources checked September 12, 2026: [AWS instance price table](https://docs.aws.amazon.com/prescriptive-guidance/latest/optimize-costs-microsoft-workloads/right-size-selection.html),
[VPC IPv4 pricing](https://aws.amazon.com/vpc/pricing/),
[gp3 price comparison](https://docs.aws.amazon.com/emr/latest/ManagementGuide/emr-plan-storage-compare-volume-types.html).
Account credits or free allowances have not been assumed.

## Commands

Read-only planning (no uploads, resource creation or permission changes):

```sh
uv run --frozen python tools/deploy_aws.py plan
```

It writes `outputs/deployment/template.json` and `plan.json`. The template has no
password or personal AWS credential. Deployment has been approved for this setup:

```sh
uv run --frozen python tools/deploy_aws.py deploy
uv run --frozen python tools/deploy_aws.py status
```

Wait for CREATE_COMPLETE of the server stage. If it fails, inspect stack events and
Systems Manager logs before retrying. Bootstrap signals success
only after the data disk is mounted, dependencies installed and `/health` returns
success. Then run `uv run --frozen python tools/deploy_aws.py advance` to add the
VPC origin. Wait for UPDATE_COMPLETE and the origin's actual Deployed status;
run `advance` again to add CloudFront. The command checks readiness before making
the association. Origin creation can take about 15 minutes, plus distribution
setup. The script refuses to recreate an existing stack.

Configure the exact HTTPS origin once the distribution URL exists:

```sh
uv run --frozen python tools/deploy_aws.py configure
```

This sends a Systems Manager command to set `PANTRY_PUBLIC_URL` and restart the
service. Its command ID and URL are saved in `outputs/deployment/live.json`.
Verify the command succeeded, HTTPS `/health` returns 200, anonymous visitors
receive isolated replays, and a live agent run completes all eight
comparisons using the **instance role**. Test a synthetic evidence update and
partial/final confirmation, then restart the service and verify receipts persist.
Run `uv run --frozen python tools/verify_deployment.py --no-agent --restart-service --output outputs/deployment/new-boundary-check` to exercise the public HTTP
boundary. A new output directory is required to preserve earlier evidence. The
four-stage live loop has its own command:

```sh
uv run --frozen python -m tools.verify_investigation --url https://d1vhm9p26zmdc7.cloudfront.net --output outputs/deployment/new-investigation-check
```

It uses four live starts and pauses follow-ups afterward. Remote verification is
established by that report and the service-restart persistence checks; both passed for this deployment.

Code-only updates preserve the data volume:

```sh
uv run --frozen python tools/deploy_aws.py update-code
```

Use Systems Manager Run Command for `systemctl status pantry-recall` and
`journalctl -u pantry-recall`; no SSH key is created. Check command completion,
not only the returned command ID. The updater stops the service before replacing
files and syncing the lockfile. Old application files are not pruned automatically.

## Persistence and teardown

The registry is `/var/lib/pantry/pantry.sqlite3`; visitor databases live in its
`visitors/` subdirectory on the retained volume. There is one service process;
multiple instance replicas are unsupported.
Service restarts preserve source bytes, versions, tasks and receipts. To rebuild a deleted stack using its retained disk, pass
`--data-volume vol-...` to `deploy`. The script verifies the disk is detached,
encrypted and tagged for Pantry, chooses its original availability zone and
reattaches it. Bootstrap mounts an existing filesystem without formatting it.
An explicitly supplied recovery disk remains outside the new stack's lifecycle.
A failed initial create now preserves resources for diagnosis; inspect the
service journal before retrying or explicitly removing those resources. No automatic backup schedule or failover
is configured in this minimal demo.

After the demo, delete the `pantry-recall-demo` stack to remove the instance,
CloudFront resources and runtime role. Before any irreversible data cleanup,
export a consistent SQLite backup and retain the source/evaluation records.
The 8 GB disk and private versioned S3 bucket intentionally remain; removing their
contents and all S3 versions is a separate destructive operation. Stopping only
the instance pauses compute charges but does not remove storage or all other costs.

## Local checks

```sh
uv run --frozen python -m unittest discover -s tests -v
node --check pantry_recall/static/app.js
```

112 tests pass. The private-mode HTTP tests cover authentication, origin rejection, source
isolation, missing versus mismatching evidence, stale versions, explicit
attestation, quantity/type guards, partial/full confirmation, replay, persistence,
agent concurrency/daily bounds, and withholding incomplete/stale model prose.
The browser preview also completed a live 8-stock Bedrock run and the full
missing-evidence → affected → 2-box partial → 4-box completed-hold flow.
Eight additional public-mode tests cover no-password entry, isolated evidence,
cross-visitor confirmation rejection, restart without audit deletion, global
agent limits across visitors and process restarts, cookie expiry and capacity.
Investigation and follow-up tests additionally cover free case selection, current
task/citation bindings, exact change evidence, incomplete coverage, partial model
failures, stale plans, coalescing, quota exhaustion, pause/reset and restart recovery.

The release-archive test checks startup using only uploaded files, so a runtime
import cannot silently depend on an omitted development tool.
