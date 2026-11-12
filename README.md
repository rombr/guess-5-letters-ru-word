# guess-5-letters-ru-word

Telegram assistant for finding Russian five-letter words.

### Install and run:

```shell
python -m pip install -r requirements.txt
TELEGRAM_API_TOKEN=<token> python bot.py
```

### Docker

Build the image and run it with your Telegram bot token:

```shell
docker build -t guess-5-letters-ru-word .
export TELEGRAM_API_TOKEN=<token>
docker run --rm -e TELEGRAM_API_TOKEN guess-5-letters-ru-word
```

The image uses Python 3.14.10 and runs as a non-root user. Session data resets
when the container restarts.

### Tests

Run offline tests (no Telegram token or network access needed):

```shell
python -m unittest discover -s tests -v
```
