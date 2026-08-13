# Frontend — Crowd Flow Optimiser Command Center

React + Vite + Recharts + React Three Fiber digital twin.

## Run

```bash
npm install
npm run dev
```

`VITE_API_BASE_URL` defaults to `http://localhost:8000` (see `.env.example`).

## Structure

```text
src/
  api/           REST clients
  components/    Command center panels + 3D twin + HF vision
  hooks/         bootstrap + simulation actions
  pages/         CommandCenter
  utils/         formatting + 3D layout
```

## Notes

- All KPI/risk/route/intervention values come from the API  
- Vision panel never invents detections  
- 3D twin only visualizes backend graph + zone telemetry  
