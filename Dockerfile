FROM python:3.6-alpine3.11

WORKDIR /gns3server

ENV LANG en_US.UTF-8
ENV LANGUAGE en_US:en
ENV LC_ALL en_US.UTF-8
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONBUFFERED 1

COPY ./requirements.txt /gns3server/requirements.txt

RUN set -eux \
  && apk add --no-cache --virtual .build-deps build-base \
     gcc libc-dev musl-dev linux-headers python3-dev \
     vpcs qemu libvirt ubridge \
  && pip install --no-cache-dir --upgrade pip setuptools wheel \
  && pip install --no-cache-dir -r /gns3server/requirements.txt

COPY . /gns3server
RUN python3 setup.py install
