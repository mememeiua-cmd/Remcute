# Remcute

## Project Overview
A React + Vite web application running on Replit.

## Architecture
- **Frontend**: React (JSX) with Vite as the build tool
- **Runtime**: Node.js 20
- **Port**: 5000

## Project Structure
```
├── index.html          # HTML entry point
├── src/
│   ├── main.jsx        # React root mount
│   ├── App.jsx         # Main app component
│   └── index.css       # Global styles
├── vite.config.js      # Vite configuration (host 0.0.0.0, port 5000)
├── package.json        # Dependencies and scripts
└── .gitignore
```

## Development
- Run: `npm run dev` (starts Vite dev server on 0.0.0.0:5000)
- Build: `npm run build` (outputs to `dist/`)

## Deployment
- Type: Static site
- Build command: `npm run build`
- Public directory: `dist`
