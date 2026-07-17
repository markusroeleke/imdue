FROM python:3.11-slim

ARG GIT_VERSION=unknown
LABEL org.opencontainers.image.version="${GIT_VERSION}"

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p reports sessions uploads

EXPOSE 8060

ENV PORT=8060
CMD ["sh", "-c", "chainlit run src/app.py --host 0.0.0.0 --port ${PORT}"]
