import { spawnSync } from 'node:child_process';

const res = spawnSync('npm', ['audit', '--omit=dev', '--json'], {
  encoding: 'utf8',
  maxBuffer: 10 * 1024 * 1024,
});

let data = {};
try {
  data = JSON.parse(res.stdout || '{}');
} catch (err) {
  console.error('Failed to parse npm audit output:', err);
  process.exit(1);
}

const vulns = data.vulnerabilities || {};

function isPicoRelated(pkgName, visited = new Set()) {
  if (pkgName === 'picomatch') return true;
  if (visited.has(pkgName)) return false;
  visited.add(pkgName);
  const v = vulns[pkgName];
  if (!v || !v.via) return false;
  for (const via of v.via) {
    if (typeof via === 'string') {
      if (isPicoRelated(via, visited)) return true;
    } else if (typeof via === 'object') {
      if (via.name === 'picomatch' || via.url?.includes('GHSA-fc5q-39xc-vjpf')) return true;
    }
  }
  return false;
}

const unignored = [];
for (const [name, v] of Object.entries(vulns)) {
  if (v.severity === 'high' || v.severity === 'critical') {
    const realVia = (v.via || []).filter((x) => typeof x === 'object');
    const nonPicoRoots = realVia.filter(
      (x) => x.name !== 'picomatch' && !x.url?.includes('GHSA-fc5q-39xc-vjpf')
    );
    if (nonPicoRoots.length > 0) {
      unignored.push({ name, reasons: nonPicoRoots });
    } else {
      const stringVia = (v.via || []).filter((x) => typeof x === 'string');
      if (stringVia.length > 0 && !stringVia.every((s) => isPicoRelated(s))) {
        unignored.push({ name, reasons: stringVia });
      }
    }
  }
}

if (unignored.length > 0) {
  console.error('High or critical vulnerabilities detected (excluding unpatched GHSA-fc5q-39xc-vjpf):');
  console.error(JSON.stringify(unignored, null, 2));
  process.exit(1);
}

console.log('No unignored high/critical vulnerabilities found.');
