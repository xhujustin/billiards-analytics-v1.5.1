# Frontend PostCSS Tailwind Fix

## 06/27:'Fix frontend PostCSS missing Tailwind CSS dependency'

### Scope

When Vite fails with `Failed to load PostCSS config` and `Cannot find module 'tailwindcss'`, the frontend PostCSS config is valid but `frontend/node_modules` is missing the required Tailwind package.

Keep these dependencies in `frontend/package.json` and `frontend/package-lock.json`:

```json
{
  "tailwindcss": "^3.4.17",
  "postcss": "^8.5.15",
  "autoprefixer": "^10.5.0"
}
```

### Usage

```powershell
cd frontend
npm.cmd install tailwindcss@3.4.17 autoprefixer@10.5.0 --no-audit --no-fund
```

If Vite build fails in a restricted environment with `EPERM: operation not permitted, mkdir 'frontend\node_modules\.vite-temp'`, run the same build command from a normal Windows shell so Vite can create its temporary directory under `node_modules`.

### Expected Error

```text
[plugin:vite:css] Failed to load PostCSS config
Loading PostCSS Plugin failed: Cannot find module 'tailwindcss'
Require stack:
- frontend\postcss.config.js
```

### Verification

```powershell
cd frontend
npm.cmd run build
```

Success output includes `built`, and production files are generated under `frontend/dist`.
