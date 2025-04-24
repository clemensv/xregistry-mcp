import fs from 'fs';
import FlexSearch from 'flexsearch';
import path from 'path';
import { fileURLToPath } from 'url';

const files = [
  { name: 'server', fields: ['name', 'description'] },
  { name: 'tool', fields: ['name', 'description'] },
  { name: 'prompt', fields: ['name', 'description'] },
  { name: 'resource', fields: ['name', 'description', 'uritemplate'] }
];

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

for (const { name, fields } of files) {
const data = JSON.parse(fs.readFileSync(path.join(__dirname, '..', `${name}_index.json`), 'utf-8'));

  const index = new FlexSearch.Document({
    document: {
      id: 'id',
      index: fields
    }
  });

  if (Array.isArray(data)) {
    data.forEach(doc => index.add(doc));
  } else {
    index.add(data);
  }

  var flexdir = path.join(__dirname, '..', 'flex');
  if (!fs.existsSync(flexdir)) {
    fs.mkdirSync(flexdir, { recursive: true });
  }

  // Export each sub-index and collect
  const exportData = {};
  await index.export(async (key, data) => {
    exportData[key] = data;
  });

  fs.writeFileSync(path.join(flexdir, `${name}_index.flex.json`), JSON.stringify(exportData, null, 2));
  fs.writeFileSync(path.join(flexdir, `${name}_data.json`), JSON.stringify(data, null, 2));
}
