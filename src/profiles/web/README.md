# ProFiles Web UI

This folder contains the React, TypeScript, and Vite frontend used by the
ProFiles desktop webview and local web server.

## Prerequisites

- Node.js and npm
- Python 3.11+ for the ProFiles backend

## Production build

From the repository root, run:

```powershell
python src/profiles/web/build.py
```

The helper installs the locked npm dependencies with `npm ci` if
`node_modules` is missing, then runs the production build. You can also run it
from this folder with `python build.py`.

The build runs TypeScript checks and Vite, writing the compiled frontend to
`dist/`. The FastAPI server serves these files, and the Python package includes
them, so rebuild after changing frontend source before testing the packaged
desktop UI.

To run the commands manually from this folder:

```bash
npm ci
npm run build
```

## Local development

Install dependencies once, then start the backend and Vite in separate
terminals.

From the repository root, start the backend:

```bash
uv run ProFiles --server-only
```

From this folder, start Vite:

```bash
npm ci
npm run dev
```

Open the URL printed by Vite, normally `http://localhost:5173`. The Vite
configuration proxies `/api` requests to the backend at `http://127.0.0.1:8088`.

To preview the production build locally, run `npm run preview` after building.

## Troubleshooting

- If `npm` is not found, install Node.js with npm and reopen the terminal.
- If dependencies are out of sync, run `npm ci` from this folder.
- If the desktop UI shows stale frontend changes, rebuild and restart ProFiles;
  a browser or webview may need a hard refresh to replace cached PWA assets.
