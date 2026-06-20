const fs = require('fs');
const http = require('http');
const path = require('path');

const distDir = path.resolve(__dirname, '..', 'dist');
const port = Number(process.env.PWA_WEB_PORT || process.env.PORT || 19006);

const contentTypes = {
  '.html': 'text/html; charset=utf-8',
  '.js': 'application/javascript; charset=utf-8',
  '.json': 'application/json; charset=utf-8',
  '.webmanifest': 'application/manifest+json; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.png': 'image/png',
  '.jpg': 'image/jpeg',
  '.jpeg': 'image/jpeg',
  '.svg': 'image/svg+xml',
  '.ico': 'image/x-icon',
};

const indexPath = path.join(distDir, 'index.html');

function sendMissingIndex(res) {
  const message = `Missing ${indexPath}. Run npm run export:pwa before npm run serve:pwa.`;
  res.writeHead(503, {
    'Content-Type': 'text/plain; charset=utf-8',
    'Cache-Control': 'no-store',
  });
  res.end(message);
}

if (!fs.existsSync(indexPath)) {
  console.error(`ERROR Missing ${indexPath}. Run npm run export:pwa first.`);
  process.exit(1);
}

const server = http.createServer((req, res) => {
  const rawUrl = new URL(req.url || '/', `http://${req.headers.host || '127.0.0.1'}`);
  const pathname = decodeURIComponent(rawUrl.pathname);
  const safePath = path.normalize(pathname).replace(/^(\.\.[/\\])+/, '');
  let filePath = path.join(distDir, safePath);

  if (!filePath.startsWith(distDir)) {
    res.writeHead(403);
    res.end('Forbidden');
    return;
  }

  if (!fs.existsSync(filePath) || fs.statSync(filePath).isDirectory()) {
    filePath = indexPath;
  }

  if (!fs.existsSync(filePath)) {
    sendMissingIndex(res);
    return;
  }

  const ext = path.extname(filePath).toLowerCase();
  res.writeHead(200, {
    'Content-Type': contentTypes[ext] || 'application/octet-stream',
    'Cache-Control': ext === '.html' || ext === '.webmanifest' ? 'no-store' : 'public, max-age=31536000, immutable',
  });
  const stream = fs.createReadStream(filePath);
  stream.on('error', (error) => {
    console.error(`ERROR Failed to read PWA asset ${filePath}: ${error.message}`);
    if (!res.headersSent) {
      if (filePath === indexPath || error.code === 'ENOENT') {
        sendMissingIndex(res);
      } else {
        res.writeHead(500, {
          'Content-Type': 'text/plain; charset=utf-8',
          'Cache-Control': 'no-store',
        });
        res.end('Failed to read PWA asset.');
      }
      return;
    }
    res.destroy(error);
  });
  stream.pipe(res);
});

server.listen(port, '0.0.0.0', () => {
  console.log(`CueVex PWA static server ready: http://127.0.0.1:${port}`);
});
