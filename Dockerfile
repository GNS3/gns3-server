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
    busybox-static \
    gcc \
    qemu-kvm \
    libvirt-daemon-system

RUN apt install -y build-essential zlib1g-dev libncurses5-dev libgdbm-dev libnss3-dev libssl-dev libreadline-dev libffi-dev libsqlite3-dev wget libbz2-dev

RUN wget https://www.python.org/ftp/python/3.10.16/Python-3.10.16.tgz
RUN tar -xf Python-3.10.16.tgz
RUN cd Python-3.10.16 && ./configure --enable-optimizations && make -j 4 && make altinstall

RUN wget https://bootstrap.pypa.io/get-pip.py
RUN python3.10 get-pip.py
RUN python3.10 -m pip install --upgrade pip
RUN python3.10 -m pip install --upgrade setuptools

RUN add-apt-repository ppa:gns3/ppa && apt update && DEBIAN_FRONTEND=noninteractive apt install -y \
    vpcs \
    ubridge \
    dynamips

COPY . /gns3server

RUN mkdir -p ~/.config/GNS3/3.0/
RUN cp scripts/gns3_server.conf ~/.config/GNS3/3.0/

RUN python3.10 -m pip install .
