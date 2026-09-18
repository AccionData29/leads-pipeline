FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml requirements.txt ./
COPY pipeline ./pipeline
RUN pip install --no-cache-dir .
EXPOSE 8001
CMD ["uvicorn", "pipeline.api:app", "--host", "0.0.0.0", "--port", "8001"]
