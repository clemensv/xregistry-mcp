/**
 * Validate YAML in GitHub issue body or author comment and check existence of mcp.json file
 * Requires env: GH_TOKEN
 */
const { Octokit } = require("@octokit/rest");
const axios = require("axios");
const yaml = require("js-yaml");
const fs = require("fs");

const octokit = new Octokit({ auth: process.env.GH_TOKEN });

(async () => {
  const [owner, repo] = process.env.GITHUB_REPOSITORY.split('/');
  const event = JSON.parse(fs.readFileSync(process.env.GITHUB_EVENT_PATH, "utf8"));
  const issue_number = event.issue?.number;

  if (!issue_number) {
    console.error('❌ Could not determine issue number.');
    process.exit(1);
  }

  const { data: issue } = await octokit.rest.issues.get({ owner, repo, issue_number });
  const issueAuthor = issue.user.login;

  // Helper to extract YAML fenced block
  const extractYamlBlock = (text) => {
    const match = text?.match(/```yaml\s+([\s\S]+?)```/i);
    return match ? match[1] : null;
  };

  let yamlSource = extractYamlBlock(issue.body);

  if (!yamlSource) {
    // Fallback: scan comments by issue author
    const comments = await octokit.paginate(octokit.rest.issues.listComments, {
      owner,
      repo,
      issue_number
    });

    for (const comment of comments) {
      if (comment.user.login === issueAuthor) {
        yamlSource = extractYamlBlock(comment.body);
        if (yamlSource) break;
      }
    }
  }

  if (!yamlSource) {
    await octokit.rest.issues.createComment({
      owner,
      repo,
      issue_number,
      body: '❌ No valid YAML block found in the issue body or comments by the author. Expected fenced block like ```yaml ... ```.'
    });
    process.exit(0);
  }

  let config;
  try {
    config = yaml.load(yamlSource);
  } catch (err) {
    await octokit.rest.issues.createComment({
      owner,
      repo,
      issue_number,
      body: `❌ YAML parsing error: \`${err.message}\``
    });
    process.exit(0);
  }

  const { repo: repoUrl, path = '', branch = 'main' } = config;

  if (!repoUrl) {
    await octokit.rest.issues.createComment({
      owner,
      repo,
      issue_number,
      body: '❌ YAML must contain a `repo:` field.'
    });
    process.exit(0);
  }

  let fileUrl;
  if (/github\.com/.test(repoUrl)) {
    const m = repoUrl.match(/github\.com\/([^/]+)\/([^/]+)/);
    if (!m) {
      await octokit.rest.issues.createComment({
        owner,
        repo,
        issue_number,
        body: '❌ Invalid GitHub repo URL format.'
      });
      process.exit(0);
    }
    const [_, ghOwner, ghRepo] = m;
    fileUrl = `https://raw.githubusercontent.com/${ghOwner}/${ghRepo}/${branch}/${path ? path.replace(/\/$/, '') + '/' : ''}mcp.json`;
  } else {
    fileUrl = `${repoUrl.replace(/\/$/, '')}/${path ? path.replace(/\/$/, '') + '/' : ''}mcp.json`;
  }

  try {
    const res = await axios.get(fileUrl, { timeout: 5000 });
    if (res.status !== 200) throw new Error();
  } catch {
    await octokit.rest.issues.createComment({
      owner,
      repo,
      issue_number,
      body: `❌ \`mcp.json\` not found at: \`${fileUrl}\``
    });
    process.exit(0);
  }
})();
