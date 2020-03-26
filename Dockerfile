# Dockerfile for GNS3 server development

FROM ubuntu:18.04

ENV DEBIAN_FRONTEND noninteractive

# Set the locale
ENV LANG en_US.UTF-8  
ENV LANGUAGE en_US:en  
ENV LC_ALL en_US.UTF-8 

RUN apt-get update && apt-get install -y software-properties-common
RUN add-apt-repository ppa:gns3/ppa
RUN apt-get update && apt-get install -y \
    locales \
    python3-pip \
    python3-dev \ 
    qemu-system-x86 \
    qemu-kvm \
    libvirt-bin \
    x11vnc 

RUN locale-gen en_US.UTF-8

# Install uninstall to install dependencies
RUN apt-get install -y vpcs ubridge

ADD . /server
WORKDIR /server

RUN pip3 install -r /server/requirements.txt

EXPOSE 3080

CMD python3 -m gns3server
