FROM python:3.5.4-jessie

LABEL maintainer="arnaud.hatzenbuhler@gmail.com"

ENV MONGO_HOST=mongo MONGO_PORT=27017

COPY ./brisebois /brisebois
RUN pip install --no-cache-dir -r /brisebois/requirements.txt
WORKDIR /brisebois
CMD ["python", "bot.py"]
