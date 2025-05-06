/**
 * Validate YAML in GitHub issue body and check existence of mcp.json file
 * Requires env: GH_TOKEN
 */
const { Octokit } = require("@octokit/rest");
const axios = require("axios");
const yaml = require("js-yaml");

const octokit = new Octokit({ auth: process.env.GH_TOKEN });

(async () => {
  const [owner, repo] = process.env.GITHUB_REPOSITORY.split('/');
  const issue_number = process.env.GITHUB_EVENT_PATH
    ? require(process.env.GITHUB_EVENT_PATH).issue.number
    : null;

  if (!issue_number) {
    console.error('❌ Could not determine issue number.');
    process.exit(1);
  }

  const { data: issue } = await octokit.rest.issues.get({ owner, repo, issue_number });
  const body = issue.body;

  const match = body.match(/```yaml\s+([\s\S]+?)```/i);
  if (!match) {
    await octokit.rest.issues.createComment({
      owner,
      repo,
      issue_number,
      body: '❌ No valid YAML block found in the issue. Expected fenced block like ```yaml ... ```.'
    });
    process.exit(0);
  }

  let config;
  try {
    config = yaml.load(match[1]);
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
