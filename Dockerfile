FROM python:3.11-slim

RUN apt-get update && apt-get install -y curl && apt-get clean

WORKDIR /app

COPY . /app

RUN pip install --no-cache-dir ".[exporter]"

EXPOSE 9101

CMD ["python", "-m", "nodescraper.exporter"]

#docker build -t node-scraper-exporter .
#docker run -p 9101:9101 node-scraper-exporter
# view at localhost:9101/metrics
