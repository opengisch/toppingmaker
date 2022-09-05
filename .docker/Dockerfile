ARG QGIS_TEST_VERSION=latest
FROM  opengisch/qgis:${QGIS_TEST_VERSION}
MAINTAINER Matthias Kuhn <matthias@opengis.ch>

RUN apt-get update \
    && apt-get install -y \
         python3-pip \
    && rm -rf /var/lib/apt/lists/*

RUN pip3 install pytest

ENV LANG=C.UTF-8

WORKDIR /
