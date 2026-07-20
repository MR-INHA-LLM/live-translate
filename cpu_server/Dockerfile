# CPU draft 서버 이미지 (GPU 없는 배포용). torch는 CPU 휠, transformers는 HunYuan
# 아키텍처를 네이티브 지원하는 버전으로 핀. 모델은 런타임에 ./models 로 마운트.
FROM python:3.12-slim

WORKDIR /app

# CPU torch + transformers(HunYuanDenseV1 네이티브 지원) + 서버 의존성.
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu \
 && pip install --no-cache-dir \
      "transformers==5.14.1" "fastapi>=0.115" "uvicorn>=0.30" \
      sentencepiece accelerate

COPY cpu_server/ /app/cpu_server/

ENV DRAFT_MODEL_PATH=/models/HY-MT1.5-1.8B \
    SERVED_MODEL_NAME=hy-mt1.5-1.8b

EXPOSE 8000
CMD ["uvicorn", "cpu_server.app:app", "--host", "0.0.0.0", "--port", "8000", "--log-level", "warning"]
