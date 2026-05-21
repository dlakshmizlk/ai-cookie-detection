FROM python:3.14-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    chromium \
    xvfb \
    xauth \
  && rm -rf /var/lib/apt/lists/*

# Your code expects Chromium at /snap/bin/chromium
RUN mkdir -p /snap/bin && ln -s /usr/bin/chromium /snap/bin/chromium

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["sh", "-c", "echo CONTAINER STARTED; xvfb-run -a python -u -m src.main"]