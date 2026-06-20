const fs = require('fs');
const path = require('path');

const distDir = path.resolve(__dirname, '..', 'dist');
const htmlPath = path.join(distDir, 'index.html');
const manifestPath = path.join(distDir, 'manifest.webmanifest');

if (!fs.existsSync(htmlPath)) {
  throw new Error(`Missing ${htmlPath}. Run expo export --platform web first.`);
}

const findLogoAsset = () => {
  const assetsDir = path.join(distDir, 'assets');
  const stack = [assetsDir];
  while (stack.length) {
    const current = stack.pop();
    if (!current || !fs.existsSync(current)) continue;
    for (const entry of fs.readdirSync(current, { withFileTypes: true })) {
      const fullPath = path.join(current, entry.name);
      if (entry.isDirectory()) {
        stack.push(fullPath);
      } else if (/cuevex-logo\..*\.png$/i.test(entry.name) || entry.name === 'cuevex-logo.png') {
        return `/${path.relative(distDir, fullPath).replace(/\\/g, '/')}`;
      }
    }
  }
  return '/assets/cuevex-logo.png';
};

const iconSrc = findLogoAsset();
const pwaApiBaseUrl = (process.env.EXPO_PUBLIC_MOBILE_API_URL || '').trim().replace(/\/+$/, '');
const pwaVersion = 'pwa-20260620-profile-qr-03';
const manifest = {
  name: 'CueVex',
  short_name: 'CueVex',
  id: `/?v=${pwaVersion}`,
  start_url: `/?v=${pwaVersion}`,
  scope: '/',
  display: 'standalone',
  orientation: 'portrait',
  background_color: '#ffffff',
  theme_color: '#ffffff',
  icons: [
    { src: iconSrc, sizes: '192x192', type: 'image/png', purpose: 'any maskable' },
    { src: iconSrc, sizes: '512x512', type: 'image/png', purpose: 'any maskable' },
  ],
};

fs.writeFileSync(manifestPath, `${JSON.stringify(manifest, null, 2)}\n`);

const pwaHead = [
  `<script>(function(){var version=${JSON.stringify(pwaVersion)};var url=new URL(window.location.href);if(!url.searchParams.get("v")){url.searchParams.set("v",version);window.location.replace(url.toString());}})();</script>`,
  `<script>window.__CUEVEX_PWA_API_BASE_URL__=${JSON.stringify(pwaApiBaseUrl).replace(/</g, '\\u003c')};</script>`,
  `<meta name="cuevex-api-base-url" content="${pwaApiBaseUrl.replace(/&/g, '&amp;').replace(/"/g, '&quot;')}" />`,
  '<meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1, user-scalable=no, viewport-fit=cover" />',
  '<meta name="mobile-web-app-capable" content="yes" />',
  '<meta name="apple-mobile-web-app-capable" content="yes" />',
  '<meta name="apple-mobile-web-app-title" content="CueVex" />',
  '<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent" />',
  '<meta name="theme-color" content="#ffffff" />',
  '<link rel="manifest" href="/manifest.webmanifest" />',
  `<link rel="apple-touch-icon" href="${iconSrc}" />`,
].join('\n    ');

let html = fs.readFileSync(htmlPath, 'utf8');
html = html
  .replace(/<meta name="viewport"[^>]*>\s*/gi, '')
  .replace(/<meta name="cuevex-api-base-url"[^>]*>\s*/gi, '')
  .replace(/<script>\(function\(\)\{var version=[\s\S]*?window\.location\.replace[\s\S]*?<\/script>\s*/gi, '')
  .replace(/<script>window\.__CUEVEX_PWA_API_BASE_URL__=[\s\S]*?<\/script>\s*/gi, '')
  .replace(/<meta name="apple-mobile-web-app-capable"[^>]*>\s*/gi, '')
  .replace(/<meta name="mobile-web-app-capable"[^>]*>\s*/gi, '')
  .replace(/<meta name="apple-mobile-web-app-title"[^>]*>\s*/gi, '')
  .replace(/<meta name="apple-mobile-web-app-status-bar-style"[^>]*>\s*/gi, '')
  .replace(/<meta name="theme-color"[^>]*>\s*/gi, '')
  .replace(/<link rel="manifest"[^>]*>\s*/gi, '')
  .replace(/<link rel="apple-touch-icon"[^>]*>\s*/gi, '');

if (!html.includes('</head>')) {
  throw new Error('index.html does not contain </head>.');
}

html = html.replace(
  /<style id="expo-reset">([\s\S]*?)<\/style>/,
  `<style id="expo-reset">
      html,
      body,
      #root {
        width: 100%;
        height: 100%;
        min-height: 100%;
        margin: 0;
        padding: 0;
        background: #ffffff;
        overscroll-behavior: none;
      }
      html,
      body {
        overflow: hidden;
        touch-action: manipulation;
        -webkit-text-size-adjust: 100%;
        -webkit-overflow-scrolling: touch;
      }
      body {
        height: 100vh;
        height: 100dvh;
        min-height: 100vh;
        min-height: 100dvh;
        position: relative;
      }
      #root {
        display: flex;
        height: 100dvh;
        min-height: 100dvh;
        flex: 1;
        overflow: hidden;
        position: relative;
        z-index: 1;
      }
      @supports (padding: env(safe-area-inset-bottom)) {
        body::after {
          content: "";
          position: fixed;
          left: 0;
          right: 0;
          bottom: 0;
          height: env(safe-area-inset-bottom);
          background: #ffffff;
          pointer-events: none;
          z-index: 0;
        }
      }
    </style>`
);

html = html.replace(/\s*<\/head>/, `\n    ${pwaHead}\n  </head>`);
fs.writeFileSync(htmlPath, html);

console.log(`Patched PWA HTML: ${htmlPath}`);
console.log(`Manifest: ${manifestPath}`);
