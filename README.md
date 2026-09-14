# Pantry Recall Response Agent

A Strands agent on Amazon Bedrock helps a food pantry check recalled inventory,
request missing label evidence, and track human-confirmed stock holds.

**[Live demo](https://d1vhm9p26zmdc7.cloudfront.net)** ? no password or AWS account
required. The demo uses historical recall notices and synthetic inventory.

## Run locally

Requires Python 3.11+, [uv](https://docs.astral.sh/uv/), and an AWS profile with
Bedrock access to `amazon.nova-lite-v1:0` in `us-east-1` for live agent runs.

```sh
git clone https://github.com/shinushibu17/pantry-recall-response-agent.git
cd pantry-recall-response-agent
uv sync --frozen
```

Set your AWS profile and start the app. In PowerShell:

```powershell
$env:AWS_PROFILE = "your-profile"
$env:AWS_REGION = "us-east-1"
uv run --frozen python -m pantry_recall.web
```

Open **http://127.0.0.1:8080**. Local live inference uses your AWS account.
See the [walkthrough and setup guide](docs/submission/JUDGE-GUIDE.md) for details.

## Tests

```sh
uv run --frozen --group evaluation python -m pantry_recall.evaluate --tests
```

Runs the tests, both recall fixtures and workflow checks without model calls.

## Results

| Check | Result |
| --- | --- |
| Automated tests | **159 passed** |
| Frozen recall scenarios | **18/18** across Pearl Milling and Jif |
| Recorded public agent workflow | **4/4 stages completed** |
| Separate SemEval ST1 benchmark | **0.7892** best completed test composite on 997 reports |

ST1 measures a separate classifier, not the deployed agent. It is a comparison
on an already exposed test set, not an accuracy percentage. Full
[benchmark results](evaluation/README.md) and
[agent evidence](docs/submission/EVIDENCE.md) include failures and limitations.

## Architecture

Strands and Nova Lite investigate cases through typed tools. Deterministic code
checks recall scope; separate human endpoints record confirmations. SQLite on
EBS stores events and evidence. EC2 runs the app behind CloudFront HTTPS.

[Architecture diagram](docs/submission/architecture.png) ?
[Agent design](docs/AGENT-ROLE.md) ? [Deployment](docs/DEPLOYMENT.md)

The prototype supports two reviewed product projections, has no live recall
feed, and is not field-validated. Agent recommendations cannot confirm physical
actions. The shared demo allows 20 agent starts per UTC day.

## License

[Apache 2.0](LICENSE) for project code. Recall sources retain their attribution;
the SemEval dataset has [separate terms](evaluation/semeval-st1/DATA-LICENSE.md).
