# Submission packet — September 14, 2026

Project: **Pantry Recall Response Agent** · Suggested track: **Good Neighbor**

The materials below describe the implemented project. The source repository is
public on GitHub. You still publish the article, video and hackathon entry from
your own accounts.

| Submission field / asset | Ready material |
| --- | --- |
| Name, tagline, project story, technologies | [DEVPOST.md](DEVPOST.md) |
| Live project / testing instructions | [JUDGE-GUIDE.md](JUDGE-GUIDE.md) |
| Architecture image | [architecture.png](architecture.png) — upload-ready image; [SVG](architecture.svg) and [editable diagram](architecture.mmd) |
| Evidence and results | [EVIDENCE.md](EVIDENCE.md), with portable JSON records in [evidence](evidence/) |
| Separate published-dataset evaluation | [All experiment results](../../evaluation/README.md): best completed ST1 **0.7892** on 997 reports; **0.90 target not reached**; regressions and validation failures preserved |
| Video narration and screen sequence | [VIDEO-SCRIPT.md](VIDEO-SCRIPT.md) — record and upload the actual video |
| Optional AWS Builder Center article | [BUILDER-ARTICLE.md](BUILDER-ARTICLE.md) — review and publish in your account |
| Public source repository | [shinushibu17/pantry-recall-response-agent](https://github.com/shinushibu17/pantry-recall-response-agent) |
| AWS Builder ID | Pending your account identifier |

## Finish and submit

1. Review the project story and article in your own voice. The article is a draft,
   not a claim that it has already been published or earned a bonus.
2. The [public GitHub repository](https://github.com/shinushibu17/pantry-recall-response-agent) is ready. For future updates, retain
   `pantry_recall/`, `tests/`, `tools/`, `fixtures/`, `evaluation/`, `deployment/`,
   `docs/`, `README.md`, `CLAUDE.md`, `pyproject.toml`, `uv.lock`, `.gitignore`, and
   `LICENSE`. Retain source attribution and fixture provenance. Review the staged
   file list before each push; exclude `.venv/`, `.env*`, `outputs/`, databases,
   AWS credentials and local account/deployment reports. The selected portable
   evidence in this packet is intended to be included. The existing project
   license is Apache-2.0; official notice content retains its source attribution.
3. Open the repository in a signed-out browser. Confirm the license, diagram,
   source notices, setup commands, and evidence links are visible. The README
   contains historical references to ignored local `outputs/`; use this packet's
   portable records for the public evidence trail.
4. Record the browser walkthrough using [VIDEO-SCRIPT.md](VIDEO-SCRIPT.md).
   Keep the finished demo and pitch at or below five minutes and upload it
   publicly to YouTube or Vimeo. Test the video link while signed out.
5. Fill the entry with [DEVPOST.md](DEVPOST.md), the public repository and video
   URLs, the architecture image, your AWS Builder ID, and the public demo URL.
   Add the Builder Center article URL if you publish the optional article.
6. Preview the full entry, check all links, review the competition terms, and
   submit from your account. Save the submission confirmation.

The official deadline is **September 14, 2026 at 5 p.m. Pacific / 8 p.m. Eastern**.
The rules also require project access through judging, which ends October 8.
Confirm the requirements on the [official rules page](https://agentsforhumans.devpost.com/rules)
when submitting.

## Demo availability

Public URL: **https://d1vhm9p26zmdc7.cloudfront.net**. No password is needed.

The deployment currently shares 20 live agent starts per UTC day and permits
one run at a time. The full recording sequence uses four starts. Check remaining
allowance before recording and leave capacity for reviewers. Anonymous replay
allocation is also bounded at 200, and sessions last seven days. These limits
need monitoring during judging; an available webpage alone does not prove that
a new reviewer can start inference. Pause follow-ups after your recording.

There is no need to add AgentCore, another agent, or more UI before submitting
this version. The useful remaining work is a clear recording, publication, and
maintaining a usable demo.
