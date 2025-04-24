import os
import json
import subprocess
from pathlib import Path

def clone_repo(url, dest_dir):
    if dest_dir.exists():
        return
    subprocess.run(["git", "clone", url, str(dest_dir)], check=False)


def extract_info(repo_dir):
    info = {}
    # name from folder
    info['name'] = repo_dir.name
    # description: first line of README.md
    readme = repo_dir / 'README.md'
    if readme.exists():
        with open(readme, 'r', encoding='utf-8') as f:
            for line in f:
                if line.strip():
                    info['description'] = line.strip()
                    break
    else:
        info['description'] = ''
    # version: from package.json or default
    pkg = repo_dir / 'package.json'
    if pkg.exists():
        try:
            data = json.loads(pkg.read_text(encoding='utf-8'))
            info['version'] = data.get('version', '')
        except json.JSONDecodeError:
            info['version'] = ''
    else:
        info['version'] = ''
    return info


def generate_manifest(entry, repos_root, out_dir):
    url = entry['repository']['url']
    repo_name = url.rstrip('/').split('/')[-1]
    dest = repos_root / repo_name
    clone_repo(url, dest)
    info = extract_info(dest)

    manifest = {
        'mcpVersion': '1.0.0',
        'serverVersion': info.get('version', ''),
        'name': info.get('name'),
        'description': info.get('description'),
        'repository': {
            'url': url,
            'name': repo_name,
            'subfolder': entry['repository'].get('subfolder', ''),
            'branch': entry['repository'].get('branch', ''),
            'commit': entry['repository'].get('commit', '')
        },
        'endpoints': {},
        'deployment': {}
    }

    out_file = out_dir / f"{repo_name}-manifest.json"
    with open(out_file, 'w', encoding='utf-8') as f:
        json.dump(manifest, f, indent=2)
    print(f"Generated manifest: {out_file}")


def main():
    root = Path(__file__).parent
    seed = root / 'seed.json'
    repos_root = root / 'repos'
    out_dir = root / 'manifests'
    repos_root.mkdir(exist_ok=True)
    out_dir.mkdir(exist_ok=True)

    with open(seed, 'r', encoding='utf-8') as f:
        entries = json.load(f)

    for entry in entries:
        repo = entry.get('repository', {})
        url = repo.get('url')
        if not url:
            continue
        generate_manifest(entry, repos_root, out_dir)

if __name__ == '__main__':
    main()