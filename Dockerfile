FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app
COPY pyproject.toml README.md LICENSE-PROVISIONAL.md ./
COPY src ./src
COPY policies ./policies
COPY formal ./formal
COPY docs ./docs

RUN python -m pip install --no-cache-dir .

ENTRYPOINT ["veritas"]
CMD ["demo"]

