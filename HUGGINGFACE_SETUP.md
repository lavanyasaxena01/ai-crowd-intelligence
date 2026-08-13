# Hugging Face Setup — Crowd Flow Optimiser

The Grand Prix brief requires a **real Hugging Face Hub** integration.

This project uses Hub **object detection** for optional venue/CCTV still analysis.

## Model

Default:

```text
facebook/detr-resnet-50
```

Override with `HF_MODEL` if needed.

## Create a token

1. Create/login to your Hugging Face account: https://huggingface.co/join  
2. Create an access token: https://huggingface.co/settings/tokens  
3. Copy the token (read permission is enough for Inference API).

## Configure backend

```bash
cd backend
copy .env.example .env
```

Edit `backend/.env`:

```env
HF_TOKEN=hf_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
HF_MODEL=facebook/detr-resnet-50
```

Never commit `.env`.

## Install vision deps

```bash
cd backend
venv\Scripts\activate
pip install huggingface_hub Pillow python-dotenv python-multipart
```

(or `pip install -r requirements.txt`)

## API

- `GET /api/vision/status` — whether token/model are configured  
- `POST /api/vision/analyze` — multipart form field `file` (image)

## Frontend

Command Center → **Hugging Face Vision Intelligence**

1. Upload an image  
2. Click **ANALYZE WITH HUGGING FACE**  
3. View people count + bounding boxes (when returned)

## If inference fails

- Missing token → clear configuration message (no fake detections)  
- Network/rate-limit → API returns the Hub error text  
- Invalid image → 400 with explanation  

## Implemented vs optional

| Feature | Status |
|---|---|
| HF Hub object detection on uploaded stills | **Implemented** |
| Live CCTV stream ingestion | Optional / future |
| Production camera deployment | Optional / future |
