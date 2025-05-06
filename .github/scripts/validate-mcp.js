/**
 * Validate YAML in GitHub issue body or author comment and process mcp.json
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
      body: '❌ No valid YAML block found in the issue body or comments by the author.'
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

  const { repo: repoUrl, path = '', branch = 'main', mcpprovider = '', server = '' } = config;

  if (!repoUrl || !mcpprovider || !server) {
    await octokit.rest.issues.createComment({
      owner,
      repo,
      issue_number,
      body: '❌ YAML must contain `repo:`, `mcpprovider:`, and `server:` fields.'
    });
    process.exit(0);
  }

  const normalizedPath = path.replace(/\/$/, '');
  const mcpFilePath = normalizedPath ? `${normalizedPath}/mcp.json` : 'mcp.json';
  const indexRelPath = pathModule.join('registry', 'mcpproviders', mcpprovider, 'servers', server, 'index.json');

  const tempDir = fs.mkdtempSync(pathModule.join(os.tmpdir(), 'mcp-check-'));

  try {
    // Clone repo
    const repoClone = repoUrl.startsWith('http') && !repoUrl.includes('github.com')
      ? repoUrl
      : `https://github.com/${repoUrl.replace(/^https?:\/\/github.com\//, '')}`;

    let ghOwner, ghRepo;
    if (repoUrl.startsWith('http')) {
      const m = repoUrl.match(/github\.com\/([^/]+)\/([^/]+)(\.git)?/);
      if (!m) {
        await octokit.rest.issues.createComment({
          owner,
          repo,
          issue_number,
          body: '❌ Invalid GitHub repo URL.'
        });
        process.exit(0);
      }
      [, ghOwner, ghRepo] = m;
    } else {
      const m = repoUrl.match(/^([^/]+)\/([^/]+)$/);
      if (!m) {
        await octokit.rest.issues.createComment({
          owner,
          repo,
          issue_number,
          body: '❌ Invalid relative repo format. Use `owner/repo`.'
        });
        process.exit(0);
      }
      [, ghOwner, ghRepo] = m;
    }


    execSync(`git clone --depth 1 --branch ${branch} ${repoClone} ${tempDir}`, { stdio: 'ignore' });

    const absMcpPath = pathModule.join(tempDir, mcpFilePath);
    if (!fs.existsSync(absMcpPath)) {
      await octokit.rest.issues.createComment({
        owner,
        repo,
        issue_number,
        body: `❌ \`mcp.json\` not found at: \`${mcpFilePath}\` in \`${repoClone}@${branch}\``
      });
      process.exit(0);
    }

    const absIndexPath = pathModule.join(tempDir, indexRelPath);
    if (fs.existsSync(absIndexPath)) {
      await octokit.rest.issues.createComment({
        owner,
        repo,
        issue_number,
        body: `❌ \`index.json\` already exists at registry path: \`/registry/mcpproviders/${mcpprovider}/servers/${server}/index.json\``
      });
      process.exit(0);
    }

    // Write index.json
    fs.mkdirSync(pathModule.dirname(absIndexPath), { recursive: true });
    fs.copyFileSync(absMcpPath, absIndexPath);

    // Commit and push
    execSync(`git config user.name "github-actions[bot]"`, { cwd: tempDir });
    execSync(`git config user.email "github-actions[bot]@users.noreply.github.com"`, { cwd: tempDir });
    execSync(`git add "${absIndexPath}"`, { cwd: tempDir });
    execSync(`git commit -m "Add index.json for ${mcpprovider}/${server}"`, { cwd: tempDir });
    execSync(`git remote set-url origin https://github.com/${ghOwner}/${ghRepo}.git`, { cwd: tempDir });
    execSync(`git config --local credential.helper "!f() { echo username=x-access-token; echo password=${process.env.GH_TOKEN}; }; f"`, { cwd: tempDir });
    execSync(`git push origin ${branch}`, { cwd: tempDir, stdio: 'ignore' });

    // Close issue
    await octokit.rest.issues.update({
      owner,
      repo,
      issue_number,
      state: 'closed'
    });

    await octokit.rest.issues.createComment({
      owner,
      repo,
      issue_number,
      body: `✅ \`mcp.json\` registered successfully at \`/registry/mcpproviders/${mcpprovider}/servers/${server}/index.json\`.`
    });

  } catch (err) {
    await octokit.rest.issues.createComment({
      owner,
      repo,
      issue_number,
      body: `❌ Operation failed: \`${err.message}\``
    });
    process.exit(1);
  } finally {
    rmSync(tempDir, { recursive: true, force: true });
  }
})();
