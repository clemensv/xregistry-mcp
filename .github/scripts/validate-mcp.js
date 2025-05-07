/**
 * Validate YAML in GitHub issue body or author comment and process mcp.json.
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
  const ghOwner = owner;
  const ghRepo = repo;

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

  const {
    repo: repoUrl,
    path = '',
    branch: externalBranch = 'main',
    mcpprovider = '',
    server = ''
  } = config;

  // RFC3986 unreserved + "@" validation
  const VALID_NAME_REGEX = /^[A-Za-z0-9_][A-Za-z0-9._~@-]{0,127}$/;
  
  if (!repoUrl || !mcpprovider || !server) {
    await octokit.rest.issues.createComment({
      owner,
      repo,
      issue_number,
      body: '❌ YAML must contain non-empty `repo:`, `mcpprovider:`, and `server:` fields.'
    });
    process.exit(0);
  }
  
  if (!VALID_NAME_REGEX.test(mcpprovider)) {
    await octokit.rest.issues.createComment({
      owner,
      repo,
      issue_number,
      body: `❌ Invalid \`mcpprovider:\` value: \`${mcpprovider}\`. Must be 1-128 characters long, start with ALPHA, DIGIT, or "_", and contain only ALPHA, DIGIT, "-", ".", "_", "~", or "@".`
    });
    process.exit(0);
  }
  
  if (!VALID_NAME_REGEX.test(server)) {
    await octokit.rest.issues.createComment({
      owner,
      repo,
      issue_number,
      body: `❌ Invalid \`server:\` value: \`${server}\`. Must be 1-128 characters long, start with ALPHA, DIGIT, or "_", and contain only ALPHA, DIGIT, "-", ".", "_", "~", or "@".`
    });
    process.exit(0);
  }


  // Determine default branch of the current repo
  const { data: repoData } = await octokit.rest.repos.get({ owner, repo });
  const localBranch = repoData.default_branch;

  // Normalize external repo URL
  let normalizedRepoUrl = repoUrl;
  let isGitHub = false;
  if (!repoUrl.startsWith('http')) {
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
    normalizedRepoUrl = `https://github.com/${m[1]}/${m[2]}`;
    isGitHub = true;
  } else if (/^https:\/\/github\.com/.test(repoUrl)) {
    isGitHub = true;
  }

  const normalizedPath = path.replace(/\/$/, '');
  const filePath = normalizedPath ? `${normalizedPath}/mcp.json` : 'mcp.json';
  const indexRelPath = pathModule.join('registry', 'mcpproviders', mcpprovider, 'servers', server, 'index.json');

  const workspaceDir = fs.mkdtempSync(pathModule.join(os.tmpdir(), 'mcp-workspace-'));
  const sourceDir = fs.mkdtempSync(pathModule.join(os.tmpdir(), 'mcp-source-'));
  const absIndexPath = pathModule.join(workspaceDir, indexRelPath);
  let absMcpPath;

  try {
    // Attempt raw HTTP fetch if GitHub
    let fileUrl;
    if (isGitHub) {
      fileUrl = normalizedRepoUrl
        .replace(/^https:\/\/github\.com/, 'https://raw.githubusercontent.com')
        + `/${externalBranch}/${filePath}`;
      try {
        const res = await axios.get(fileUrl, { timeout: 5000 });
        const dest = pathModule.join(sourceDir, 'mcp.json');
        fs.writeFileSync(dest, res.data, { encoding: 'utf-8' });
        absMcpPath = dest;
      } catch {
        fileUrl = null;
      }
    }

    // Fallback to git clone
    if (!absMcpPath) {
      try {
        execSync(`git clone --depth 1 --branch ${externalBranch} ${normalizedRepoUrl} ${sourceDir}`, { stdio: 'ignore' });
      } catch (err) {
        await octokit.rest.issues.createComment({
          owner,
          repo,
          issue_number,
          body: `❌ Failed to clone repo: \`${normalizedRepoUrl}@${externalBranch}\`\n\`\`\`\n${err.message}\n\`\`\``
        });
        process.exit(1);
      }

      absMcpPath = pathModule.join(sourceDir, filePath);
      if (!fs.existsSync(absMcpPath)) {
        await octokit.rest.issues.createComment({
          owner,
          repo,
          issue_number,
          body: `❌ \`mcp.json\` not found in cloned repo at path: \`${filePath}\``
        });
        process.exit(1);
      }
    }

    // Check if index.json already exists
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
    execSync(`git init`, { cwd: workspaceDir });
    execSync(`git config user.name "github-actions[bot]"`, { cwd: workspaceDir });
    execSync(`git config user.email "github-actions[bot]@users.noreply.github.com"`, { cwd: workspaceDir });
    execSync(`git remote add origin https://github.com/${ghOwner}/${ghRepo}.git`, { cwd: workspaceDir });
    execSync(`git fetch origin ${localBranch}`, { cwd: workspaceDir });
    execSync(`git checkout -b ${localBranch}`, { cwd: workspaceDir });
    execSync(`git pull origin ${localBranch}`, { cwd: workspaceDir });

    execSync(`git add "${indexRelPath}"`, { cwd: workspaceDir });
    execSync(`git commit -m "Add index.json for ${mcpprovider}/${server}"`, { cwd: workspaceDir });
    execSync(`git config --local credential.helper "!f() { echo username=x-access-token; echo password=${process.env.GH_TOKEN}; }; f"`, { cwd: workspaceDir });
    execSync(`git push origin ${localBranch}`, { cwd: workspaceDir, stdio: 'ignore' });

    await octokit.rest.issues.createComment({
      owner,
      repo,
      issue_number,
      body: `✅ \`index.json\` registered successfully at \`/registry/mcpproviders/${mcpprovider}/servers/${server}/index.json\`.`
    });

    await octokit.rest.issues.update({
      owner,
      repo,
      issue_number,
      state: 'closed'
    });

  } catch (err) {
    const msg = err.message.replace(process.env.GH_TOKEN, '***');
    await octokit.rest.issues.createComment({
      owner,
      repo,
      issue_number,
      body: `❌ Operation failed: \`${msg}\``
    });
    process.exit(1);
  } finally {
    fs.rmSync(workspaceDir, { recursive: true, force: true });
    fs.rmSync(sourceDir, { recursive: true, force: true });
  }
})();
