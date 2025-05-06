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
  const filePath = normalizedPath ? `${normalizedPath}/mcp.json` : 'mcp.json';
  const indexRelPath = pathModule.join('registry', 'mcpproviders', mcpprovider, 'servers', server, 'index.json');

  const workspaceDir = fs.mkdtempSync(pathModule.join(os.tmpdir(), 'mcp-workspace-'));
  const sourceDir = fs.mkdtempSync(pathModule.join(os.tmpdir(), 'mcp-source-'));
  const absIndexPath = pathModule.join(workspaceDir, indexRelPath);
  let absMcpPath;

  try {
    // Try HTTP fetch first
    let fileUrl;
    if (repoUrl.startsWith('http')) {
      const rawBase = repoUrl.replace(/^https:\/\/github\.com/, 'https://raw.githubusercontent.com');
      fileUrl = `${rawBase}/${branch}/${filePath}`;
      try {
        const res = await axios.get(fileUrl, { timeout: 5000 });
        const dest = pathModule.join(sourceDir, 'mcp.json');
        fs.writeFileSync(dest, res.data, { encoding: 'utf-8' });
        absMcpPath = dest;
      } catch {
        fileUrl = null; // fall back to clone
      }
    }

    // If HTTP fetch failed or not GitHub
    if (!absMcpPath) {
      execSync(`git clone --depth 1 --branch ${branch} ${repoUrl} ${sourceDir}`, { stdio: 'ignore' });
      absMcpPath = pathModule.join(sourceDir, filePath);
      if (!fs.existsSync(absMcpPath)) {
        await octokit.rest.issues.createComment({
          owner,
          repo,
          issue_number,
          body: `❌ \`mcp.json\` not found in cloned repo at path: \`${filePath}\``
        });
        process.exit(0);
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

    // Copy to registry path
    fs.mkdirSync(pathModule.dirname(absIndexPath), { recursive: true });
    fs.copyFileSync(absMcpPath, absIndexPath);

    // Commit and push
    execSync(`git init`, { cwd: workspaceDir });
    execSync(`git config user.name "github-actions[bot]"`, { cwd: workspaceDir });
    execSync(`git config user.email "github-actions[bot]@users.noreply.github.com"`, { cwd: workspaceDir });
    execSync(`git remote add origin https://github.com/${ghOwner}/${ghRepo}.git`, { cwd: workspaceDir });
    execSync(`git fetch origin ${branch}`, { cwd: workspaceDir });
    execSync(`git checkout -b ${branch}`, { cwd: workspaceDir });
    execSync(`git pull origin ${branch}`, { cwd: workspaceDir });

    execSync(`cp -r ${absIndexPath} ${pathModule.join(workspaceDir, indexRelPath)}`, { cwd: workspaceDir });
    execSync(`git add "${indexRelPath}"`, { cwd: workspaceDir });
    execSync(`git commit -m "Add index.json for ${mcpprovider}/${server}"`, { cwd: workspaceDir });

    execSync(`git config --local credential.helper "!f() { echo username=x-access-token; echo password=${process.env.GH_TOKEN}; }; f"`, { cwd: workspaceDir });
    execSync(`git push origin ${branch}`, { cwd: workspaceDir, stdio: 'ignore' });

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
    rmSync(workspaceDir, { recursive: true, force: true });
    rmSync(sourceDir, { recursive: true, force: true });
  }
})();
