# Upload the Builder Center article

You will publish from your own Builder Center account. Nothing in this packet
has been posted automatically.

1. Create an article on [AWS Builder Center](https://builder.aws.com/).
2. Paste this title, keeping the hashtag:

   **#AgentsForHumans: Building a Pantry Recall Agent That Keeps Human Confirmation Separate**

3. Copy [BUILDER-ARTICLE.md](BUILDER-ARTICLE.md) into the article body, starting
   with “A pantry volunteer needs more than a summary...” Skip the first heading
   because the editor already has a title field. Preserve the Python code block
   and hyperlinks; check the preview if the editor does not import Markdown.
4. Upload [architecture.png](architecture.png). Place it after “Deploy a
   demonstration people can try,” or use it as the article's cover if preferred.
   Suggested alt text: “Pantry Recall Response architecture: CloudFront routes
   visitors to an EC2 Python app; a Strands agent calls Bedrock and read tools,
   while separate human endpoints persist evidence and confirmations in SQLite
   on encrypted EBS.”
5. Suggested topics, if the editor offers them: Amazon Bedrock, Strands Agents,
   generative AI, community impact. Retain **#AgentsForHumans** in the title.
6. Preview the article. Confirm the diagram and code are readable, the public
   demo link opens, and the first-person account reflects your work accurately.
   The article now links the [public source repository](https://github.com/shinushibu17/pantry-recall-response-agent).
7. Publish, then open the article while signed out. Copy its public URL into the
   hackathon entry's article field. Publishing an article does not submit the
   Devpost entry.

Live demo: https://d1vhm9p26zmdc7.cloudfront.net — no password required.

Use [DEVPOST.md](DEVPOST.md) for the separate project story and
[START-HERE.md](START-HERE.md) for the remaining submission steps. The actual
narrated video, AWS Builder ID and final entry submission
still need your account actions unless you have already completed them.

Check the [official rules](https://agentsforhumans.devpost.com/rules) before
submitting. The stated deadline is September 14, 2026, 5 p.m. Pacific / 8 p.m.
Eastern. Leave time to verify the finished entry and save its confirmation.
