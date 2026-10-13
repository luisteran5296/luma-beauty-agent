FROM python:3.12-slim
WORKDIR /code
COPY requirements-gateway.txt .
RUN pip install --no-cache-dir -r requirements-gateway.txt
COPY beauty beauty
COPY gateway gateway
ENV ENVIRONMENT=production
CMD ["uvicorn", "gateway.main:app", "--host", "0.0.0.0", "--port", "8080", "--no-access-log"]
