FROM python:3.10-slim-bookworm

WORKDIR /usr/src/app

RUN --mount=type=bind,source=requirements.txt,target=/tmp/requirements.txt \
    pip install --no-cache-dir --requirement /tmp/requirements.txt

COPY *.py .

CMD [ "python", "./party-billing-bot.py" ]
