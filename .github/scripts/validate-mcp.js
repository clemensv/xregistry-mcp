/**
 * Validate YAML in GitHub issue body or author comment and check existence of mcp.json file
 * Requires env: GH_TOKEN
 */
const { Octokit } = require("@octokit/rest");
const axios = require("axios");
const yaml = require("js-yaml");
const fs = require("fs");
const os = require("os");
const pathModule = require("path");
const { execSync, rmSync } = require("child_process");

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

  const extractYamlBlock = (text) => {
    if (!text) return null;
  
    // Match blocks like ```yaml ... ```, ~~~yaml ... ~~~, --- ... ---
    const patterns = [
      /```(?:yaml)?\s*([\s\S]+?)```/i,
      /~~~(?:yaml)?\s*([\s\S]+?)~~~/i,
      /---\s*([\s\S]+?)---/i
    ];
  
    for (const pattern of patterns) {
      const match = text.match(pattern);
      if (match) return match[1];
    }
  
    return null;
  };

  let yamlSource = extractYamlBlock(issue.body);

  if (!yamlSource) {
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

  const normalizedPath = path.replace(/\/$/, '');
  let filePath = normalizedPath ? `${normalizedPath}/mcp.json` : 'mcp.json';

  // GitHub repo - raw fetch
  if (!repoUrl.startsWith('http') || repoUrl.includes('github.com')) {
    let ghOwner, ghRepo;
    if (repoUrl.startsWith('http')) {
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
      [_, ghOwner, ghRepo] = m;
    } else {
      const m = repoUrl.match(/^([^/]+)\/([^/]+)$/);
      if (!m) {
        await octokit.rest.issues.createComment({
          owner,
          repo,
          issue_number,
          body: '❌ Invalid relative repo format. Expected `owner/repo`.'
        });
        process.exit(0);
      }
      [_, ghOwner, ghRepo] = m;
    }

    const fileUrl = `https://raw.githubusercontent.com/${ghOwner}/${ghRepo}/${branch}/${filePath}`;

    try {
      const res = await axios.get(fileUrl, { timeout: 5000 });
      if (res.status === 200) return; // ✅ Found
    } catch {
      await octokit.rest.issues.createComment({
        owner,
        repo,
        issue_number,
        body: `❌ \`mcp.json\` not found at: \`${fileUrl}\``
      });
      process.exit(0);
    }
  } else {
    // Clone and inspect non-GitHub repo
    const tempDir = fs.mkdtempSync(pathModule.join(os.tmpdir(), 'mcp-check-'));
    try {
      execSync(`git clone --depth 1 --branch ${branch} ${repoUrl} ${tempDir}`, { stdio: 'ignore' });

      const target = pathModule.join(tempDir, filePath);
      if (!fs.existsSync(target)) {
        await octokit.rest.issues.createComment({
          owner,
          repo,
          issue_number,
          body: `❌ \`mcp.json\` not found in cloned repo at path: \`${filePath}\``
        });
        process.exit(0);
      }
    } catch (err) {
      await octokit.rest.issues.createComment({
        owner,
        repo,
        issue_number,
        body: `❌ Failed to clone repo or locate \`mcp.json\`: \`${err.message}\``
      });
      process.exit(0);
    } finally {
      rmSync(tempDir, { recursive: true, force: true });
    }
  }
})();
