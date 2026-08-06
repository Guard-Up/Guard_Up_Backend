FROM python:3.13-slim

WORKDIR /app

# 일부 ML 패키지가 wheel이 없을 때 컴파일에 필요 (안전용)
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
    && rm -rf /var/lib/apt/lists/*

# torch는 CPU 전용 빌드로 먼저 설치 (기본 설치 시 CUDA판이라 용량이 몇 GB로 커짐)
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
