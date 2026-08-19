FROM python:3.11-slim
WORKDIR /app
COPY . .
RUN pip install --no-cache-dir -e .
CMD ["shop-risk", "run", "--demo"]
