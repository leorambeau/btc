FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    libqt5gui5 \
    libqt5core5a \
    libqt5widgets5 \
    libgl1-mesa-glx \
    --no-install-recommends && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV DISPLAY=:0

CMD ["python", "btc_benchmark.py"]
