FROM python:${PYTHON_VERSION}

RUN pip install -U setuptools pip

ADD requirements.txt /server/requirements.txt
ADD dev-requirements.txt /server/dev-requirements.txt

RUN pip install -r/server/dev-requirements.txt

RUN useradd -ms /bin/bash gns3

USER gns3

ADD . /server
WORKDIR /server
