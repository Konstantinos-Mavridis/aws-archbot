# ArchBot Frontend

Next.js 14 App Router frontend for ArchBot.

## Tech stack

- **Next.js 14** (App Router, `output: export` for S3 static hosting)
- **Tailwind CSS v3** for styling
- **Mermaid.js v11** for client-side diagram rendering
- **TypeScript** (strict mode)

## Local development

```bash
npm install
npm run dev          # http://localhost:3000
```

Set the backend URL:

```bash
NEXT_PUBLIC_API_URL=http://localhost:8000 npm run dev
```

## Build (static export)

```bash
npm run build        # emits ./out/ ready for S3 upload
```

## Environment variables

| Variable | Default | Description |
|---|---|---|
| `NEXT_PUBLIC_API_URL` | `http://localhost:8000` | Backend API base URL |
