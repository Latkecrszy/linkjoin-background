FROM python:3.11.1

RUN apt-get update
RUN apt-get install -y --no-install-recommends build-essential python3 python3-pip python3-dev
RUN pip3 install pipenv

# install our code
ADD . /home/docker/code/
COPY requirements.txt /home/docker/code/requirements.txt
RUN pipenv install -r /home/docker/code/requirements.txt
RUN pip3 install -r /home/docker/code/requirements.txt


# Install application requirements
RUN (cd /home/docker/code && pipenv install)



EXPOSE 80
CMD cd /home/docker/code && pipenv install -r requirements.txt && pipenv run python3 background.py