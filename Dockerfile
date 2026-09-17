FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml requirements.txt ./
COPY pipeline ./pipeline
RUN pip install --no-cache-dir .
COPY data ./data
ENTRYPOINT ["leads-pipeline"]
