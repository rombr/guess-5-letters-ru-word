FROM python:3.14.10-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && rm requirements.txt \
    && useradd --create-home --uid 10001 bot

COPY bot.py core.py russian_nouns_5_letters.txt ./

USER bot

CMD ["python", "bot.py"]
