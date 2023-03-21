FROM ubuntu:focal

WORKDIR /gns3server

RUN apt update && DEBIAN_FRONTEND=noninteractive apt install -y \
    locales \
    locales-all

ENV LANG en_US.UTF-8
ENV LANGUAGE en_US:en
ENV LC_ALL en_US.UTF-8

COPY ./requirements.txt /gns3server/requirements.txt

RUN DEBIAN_FRONTEND=noninteractive apt install -y \
    locales \
    software-properties-common \
    python3-pip \
    python3-all \
    python3-setuptools \
    python3-dev \
    busybox-static \
    gcc \
    qemu-kvm \
    libvirt-daemon-system

RUN add-apt-repository ppa:gns3/ppa && apt update && DEBIAN_FRONTEND=noninteractive apt install -y \
    vpcs \
    ubridge \
    dynamips

COPY . /gns3server

RUN mkdir -p ~/.config/GNS3/3.0/
RUN cp scripts/gns3_server.conf ~/.config/GNS3/3.0/

RUN python3 -m pip install .
