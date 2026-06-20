# Cineloom remote generation server.
# Builds on the verified ML base image (torch 2.8 + cu12.8 + diffusers 0.38 +
# sdnq 0.2 + transformers 4.57). We only add the thin web layer on top.
FROM modelbase/ai-base:cu128-torch28

WORKDIR /app

# Optional pip mirror for restricted networks: --build-arg PIP_INDEX_URL=...
ARG PIP_INDEX_URL=""
ENV PIP_INDEX_URL=${PIP_INDEX_URL}

COPY requirements.txt /app/requirements.txt
RUN python -m pip install --no-cache-dir -r /app/requirements.txt

COPY app.py /app/app.py

ENV CINELOOM_MODEL_DIR=/model \
    CINELOOM_WORK_DIR=/work \
    PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True

EXPOSE 8879

# Single worker: the LTX-2.3 pipeline is loaded once and is offload-bound;
# concurrency would only thrash GPU memory.
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8879", "--workers", "1"]
