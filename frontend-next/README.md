# REG CMU Frontend (Next.js 16)

Modern frontend for the REG CMU AI Assistant, built with **Next.js 16**, **React 19.2**, and **TypeScript**.

## Quick Start

```bash
cd frontend-next
npm install
npm run dev
```

Open [http://localhost:3000](http://localhost:3000). The backend must be running on port 5000.

## Pages

| Route    | Description                        |
| -------- | ---------------------------------- |
| `/`      | Main chat (text + voice + TTS)     |
| `/admin` | Admin portal (7 tabs, token auth)  |

## Stack

- **Next.js 16** with Turbopack dev server
- **React 19.2** with server/client components
- **Tailwind CSS 4** via `@tailwindcss/postcss`
- **Socket.IO Client** for real-time events
- **Lucide React** for icons
- **jose** for JWT handling (client-side)

## Docker

```bash
docker build -t reg01-frontend .
docker run -p 3000:3000 -e NEXT_PUBLIC_BACKEND_URL=http://backend:5000 reg01-frontend
```

## Environment

| Variable                   | Default                  |
| -------------------------- | ------------------------ |
| `NEXT_PUBLIC_BACKEND_URL`  | `http://localhost:5000`  |
