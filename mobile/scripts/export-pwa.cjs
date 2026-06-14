const fs = require('fs');
const path = require('path');
const { spawnSync } = require('child_process');

const mobileDir = path.resolve(__dirname, '..');
const rootDir = path.resolve(mobileDir, '..');
const envPath = path.join(rootDir, 'mobile-remote.env');

function readEnvFile(filePath) {
  if (!fs.existsSync(filePath)) return {};
  return Object.fromEntries(
    fs
      .readFileSync(filePath, 'utf8')
      .split(/\r?\n/)
      .map((line) => line.trim())
      .filter((line) => line && !line.startsWith('#') && line.includes('='))
      .map((line) => {
        const index = line.indexOf('=');
        return [line.slice(0, index), line.slice(index + 1)];
      }),
  );
}

const fileEnv = readEnvFile(envPath);
const apiBaseUrl = (
  process.env.EXPO_PUBLIC_MOBILE_API_URL ||
  fileEnv.PWA_API_BASE_URL ||
  fileEnv.MOBILE_PUBLIC_BASE_URL ||
  ''
).trim();

if (!apiBaseUrl || /CHANGE_ME/i.test(apiBaseUrl)) {
  console.error('ERROR PWA_API_BASE_URL must be set in mobile-remote.env before exporting PWA.');
  process.exit(1);
}

const uploadTargetBytes = process.env.EXPO_PUBLIC_MOBILE_UPLOAD_TARGET_BYTES || fileEnv.EXPO_PUBLIC_MOBILE_UPLOAD_TARGET_BYTES || '819200';
const npxCmd = process.platform === 'win32' ? 'npx.cmd' : 'npx';

const exportResult = spawnSync(npxCmd, ['expo', 'export', '--platform', 'web'], {
  cwd: mobileDir,
  env: {
    ...process.env,
    EXPO_PUBLIC_MOBILE_API_URL: apiBaseUrl,
    EXPO_PUBLIC_MOBILE_UPLOAD_TARGET_BYTES: uploadTargetBytes,
  },
  stdio: 'inherit',
  shell: process.platform === 'win32',
});

if (exportResult.error) {
  console.error(exportResult.error.message);
  process.exit(1);
}

if (exportResult.status !== 0) {
  process.exit(exportResult.status || 1);
}

const patchResult = spawnSync(process.execPath, [path.join(__dirname, 'patch-pwa-html.cjs')], {
  cwd: mobileDir,
  env: {
    ...process.env,
    EXPO_PUBLIC_MOBILE_API_URL: apiBaseUrl,
  },
  stdio: 'inherit',
});

if (patchResult.error) {
  console.error(patchResult.error.message);
  process.exit(1);
}

process.exit(patchResult.status || 0);
