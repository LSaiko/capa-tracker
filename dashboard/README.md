# dashboard

React/TS (Vite, Chart.js) CAPA board in the portfolio palette `#22d3ee` / `#f97316` / `#94a3b8`.
`npm run dev` talks to the FastAPI backend at `VITE_API_BASE` (default `http://localhost:8000`)
and falls back to an in-browser seed workflow (`src/seed.ts`) when the API does not answer or
when built with a non-root `VITE_BASE` (GitHub Pages).
