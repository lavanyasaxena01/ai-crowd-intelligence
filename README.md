# Crowd Flow Optimiser

AI-powered **Crowd Flow Optimiser** for simulating venue crowds, detecting bottlenecks, recommending safer routes, evaluating interventions, and optionally analyzing crowd stills via **Hugging Face Hub**.

## Problem (PDF)

> Crowd Flow Optimiser: Simulating and Rerouting Crowds in Real Time

Inputs:

- Venue layout (gates, walkways, concessions, emergency exits)
- Expected crowd size
- Event schedule

Pipeline:

```text
Venue + Crowd Size + Event Schedule
        ↓
Crowd Simulation
        ↓
Bottleneck Detection / Prediction
        ↓
Smart Rerouting
        ↓
Intervention / What-If
        ↓
(Optional) Hugging Face Vision
```

## Architecture

```text
backend/simulation     CrowdSimulator + VENUE_BUILDERS
backend/prediction     risk engine + model.joblib
backend/api            FastAPI thin adapter
backend/vision         Hugging Face Hub detector
frontend               React + Vite + R3F digital twin
```

## Features

| Area | Status |
|---|---|
| Multi-venue simulation | Implemented |
| Expected crowd size → arrival pressure | Implemented |
| Event schedule intensity | Implemented |
| Risk + ML bottleneck prediction | Implemented |
| Smart routing / invalid route handling | Implemented |
| Dynamic route refresh after state change | Implemented |
| Beneficial-only intervention | Implemented |
| What-if (non-destructive) | Implemented |
| 3D digital twin visualization | Implemented |
| Hugging Face Hub vision | Implemented (needs `HF_TOKEN`) |
| Live CCTV production feed | Future / optional |

## Run

### Backend

```bash
cd backend
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
# set HF_TOKEN in .env for vision
uvicorn api.app:app --host 0.0.0.0 --port 8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:5173  
API: http://localhost:8000  

See [HUGGINGFACE_SETUP.md](./HUGGINGFACE_SETUP.md) and [API_CONTRACT.md](./API_CONTRACT.md).

## Demo flow

1. Stadium · Peak Traffic  
2. Expected Crowd `30000` · Event `18:00` · Peak window `30` · Event `120` min  
3. **RUN SIMULATION**  
4. Inspect KPIs, risk, bottleneck, 3D twin  
5. Find safest route (auto-refreshes after sim)  
6. Simulate intervention  
7. Run What-If  
8. Upload crowd image → Hugging Face analyze  

## Known limitations

- Distance/travel time are area-based approximations  
- Gate redirect is modeled as arrival-rate reduction (simulator has no per-gate split API)  
- HF vision requires network + valid token; no fake detections when offline  
- Not a live production CCTV deployment  
