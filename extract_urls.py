import json
import os

def combine_urls(seed_path):
    with open(seed_path, 'r', encoding='utf-8') as f:
        entries = json.load(f)

    full_urls = []
    for entry in entries:
        repo = entry.get('repository', {})
        url = repo.get('url')
        subfolder = repo.get('subfolder', '') or ''
        if not url:
            # skip entries without a URL
            continue
        # join base URL and subfolder without duplicate slashes
        if subfolder:
            combined = f"{url.rstrip('/')}/{subfolder.lstrip('/')}"
        else:
            combined = url
        full_urls.append(combined)
    return full_urls

if __name__ == "__main__":
    # adjust path if your seed.json is elsewhere
    seed_file = os.path.join(os.path.dirname(__file__), 'seed.json')
    for u in combine_urls(seed_file):
        print(u)