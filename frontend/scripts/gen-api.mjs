// Regenerate src/api/schema.d.ts from the backend's OpenAPI spec (CLAUDE.md: no hand-written API types).
//   npm run gen:api
// Step 1 dumps the spec straight from the FastAPI app (no server needed); step 2 turns it into TS types.
// openapi-typescript runs through npx because its peer range (typescript ^5) conflicts with this
// project's TypeScript 7; npx gives it its own copy.
import { spawnSync } from 'node:child_process'
import { mkdtempSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join, resolve } from 'node:path'

const root = resolve(import.meta.dirname, '..')
const spec = join(mkdtempSync(join(tmpdir(), 'trippatch-')), 'openapi.json')

const dump = `import json; from app.main import app; open(r'${spec}', 'w', encoding='utf-8').write(json.dumps(app.openapi()))`
run('uv', ['run', 'python', '-c', dump], { cwd: resolve(root, '../backend') })
run('npx', ['--yes', 'openapi-typescript@7.13.0', `"${spec}"`, '-o', 'src/api/schema.d.ts'], {
  cwd: root,
  shell: true,
})

function run(cmd, args, options) {
  const res = spawnSync(cmd, args, { stdio: 'inherit', ...options })
  if (res.status !== 0) process.exit(res.status ?? 1)
}
