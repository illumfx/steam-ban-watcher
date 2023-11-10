# syntax=docker/dockerfile:1.4
FROM --platform=$BUILDPLATFORM python:3.10-alpine

WORKDIR /app
COPY requirements.txt /app
RUN pip3 install -r requirements.txt

COPY . .

ENV FLASK_APP app:app
ENV FLASK_ENV development
ENV FLASK_RUN_PORT 8000
ENV FLASK_RUN_HOST 0.0.0.0
#ENV PYTHONPATH=.

EXPOSE 8000

CMD ["flask", "run", "--host=0.0.0.0", "--no-reload"]