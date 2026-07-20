# 정렬 서비스 이미지 (CPU). simalign + awesome-align. transformers/torch가 vLLM·COMET과
# 충돌(D7)하므로 게이트웨이와 별도 컨테이너로 분리. 모델은 호스트 HF 캐시를 마운트해 재사용.
FROM python:3.12-slim

WORKDIR /app

RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu \
 && pip install --no-cache-dir \
      transformers simalign "fastapi>=0.115" "uvicorn>=0.30" \
      sentencepiece scipy networkx numpy

COPY aligner/ /app/aligner/

EXPOSE 8000
CMD ["uvicorn", "aligner.app:app", "--host", "0.0.0.0", "--port", "8000", "--log-level", "warning"]
