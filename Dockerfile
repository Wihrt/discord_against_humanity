FROM python:3.6.4-alpine

LABEL maintainer="arnaud.hatzenbuhler@gmail.com"

ENV MONGO_HOST=mongo MONGO_PORT=27017

COPY ./bot /bot
RUN pip install --no-cache-dir -r /bot/requirements.txt
WORKDIR /bot
CMD ["python", "bot.py"]
