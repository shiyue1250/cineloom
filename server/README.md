# Cineloom remote generation server

A small, self-contained FastAPI service that wraps the **verified** diffusers
LTX-2.3 stack and exposes an OpenAI-compatible `/v1` dialect, so the Blender
add-on's *"Cineloom Remote · LTX-2.3"* model can generate on a GPU server
instead of the editing host.

## Safe on a shared host

By design it does not disturb co-located services:

- unique container name (`cineloom-server`), image (`cineloom/server:latest`),
  and host port (`8879`);
- pinned to a single GPU via `NVIDIA_VISIBLE_DEVICES` (set `CINELOOM_GPU`);
- the 41 GB model is mounted **read-only**;
- one worker, one job at a time — the offload-bound pipeline is never thrashed.

## Run

```bash
cp .env.example .env          # set CINELOOM_GPU, CINELOOM_MODEL_DIR, CINELOOM_API_KEY
docker compose up -d --build
docker compose logs -f
curl http://localhost:8879/health
```

`.env` keys:

| Key | Default | Meaning |
|---|---|---|
| `CINELOOM_GPU` | `2` | Host GPU index to pin (`NVIDIA_VISIBLE_DEVICES`). |
| `CINELOOM_MODEL_DIR` | `/path/to/ltx23-distilled-int8` | Host path to your LTX-2.3 weights (mounted RO at `/model`). |
| `CINELOOM_API_KEY` | *(empty)* | Require a key; empty = open (internal network). |
| `CINELOOM_OFFLOAD` | `sequential` | `sequential` (~6–8 GB peak) or `model` (~10–15 GB, faster). |
| `CINELOOM_MAX_FRAMES` | `161` | Hard frame cap per shot (241/10s OOMs — verified). |

## API

```
GET  /health
POST /v1/videos        {prompt, negative_prompt, width, height, num_frames,
                        fps, num_inference_steps, guidance_scale, seed,
                        strength, image_b64?}  -> {id, status}
GET  /v1/jobs/{id}     -> {status, phase, progress, file_id?, error?}
GET  /v1/files/{id}    -> video/mp4
POST /v1/files         (multipart)  -> {file_id}
```

Auth (when `CINELOOM_API_KEY` is set) is accepted as `Authorization: Bearer …`,
`X-API-Key: …`, or `?api_key=…`.

### Example

```bash
JOB=$(curl -s -X POST http://localhost:8879/v1/videos -H 'Content-Type: application/json' \
  -d '{"prompt":"A survivor walks through a dark corridor, cinematic, film grain",
       "width":768,"height":1280,"num_frames":121,"num_inference_steps":8,"seed":7}')
ID=$(echo "$JOB" | python -c 'import sys,json;print(json.load(sys.stdin)["id"])')
# poll /v1/jobs/$ID until status=succeeded, then:
curl -s http://localhost:8879/v1/files/$ID.mp4 -o out.mp4
```

## Notes

- Loads `LTX2ConditionPipeline` from the int8 model in seconds once weights are
  in the OS page cache.
- `sequential` offload keeps the peak around 6–8 GB, so it can share a GPU with
  other workloads without OOM; `model` offload (~10–15 GB) is faster.
- `image_b64` supplies a first-frame condition for img2vid; omit it for t2v.
