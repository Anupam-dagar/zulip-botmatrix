# See readme.md for instructions on running this code.

from typing import Any
from urllib.parse import urlparse
import requests
import zipfile
import textwrap
import configparser
import os
from pathlib import Path
import docker

provision = False
docker_client = docker.from_env()

def get_config(bot_root):
    config_file = bot_root + '/config.ini'
    if not Path(config_file).is_file:
        print("No config file found")
        return False
    config = configparser.ConfigParser()
    with open(config_file) as conf:
        try:
            config.readfp(conf)
        except configparser.Error as e:
            print("Error in config file")
            display_config_file_errors(str(e), config_file)
            return False
    config = dict(config.items('deploy'))
    return config

def is_new_bot_message(message):
    msg = message['content']
    name = msg[msg.find("[")+1:msg.rfind("]")]
    url = msg[msg.find("(")+1:msg.rfind(")")]
    sender = message['sender_email']
    if name.endswith('.zip') and url.startswith('/user_uploads/'):
        file_name = sender + '-' + name
        url = url
        return True
    return False

def set_details_up(data):
    name = data['name']
    sender = data['sender']
    message = data['message']
    url = data['url']

def download_file(base_url):
    parsed_uri = urlparse(base_url)
    file_url = '{uri.scheme}://{uri.netloc}'.format(uri=parsed_uri)
    file_url = file_url + url
    r = requests.get(file_url, allow_redirects=True)
    open('bots/' + file_name, 'wb').write(r.content)

def extract_file(bot_root):
    file_name = bot_root + ".zip"
    bot_zip = zipfile.ZipFile('bots/' + file_name)
    bot_name = file_name.split('.zip')[0]
    bot_root = 'bots/' + bot_name
    bot_zip.extractall(bot_root)
    bot_zip.close()

def check_and_load_structure(bot_root):
    bot_root = "bots/" + bot_root
    config = get_config(bot_root)
    bot_file = bot_root + '/' + config['bot']
    if not Path(bot_file).is_file:
        print("Bot main file not found")
        return False
    zuliprc_file = bot_root + '/' + config['zuliprc']
    if not Path(zuliprc_file).is_file:
        print("Zuliprc file not found")
        return False
    provision = False
    if Path(bot_root + '/requirements.txt').is_file:
        "Found a requirements file"
        provision = True
    return True

def create_docker_image(bot_root):
    bot_name = bot_root
    bot_root = "bots/" + bot_root
    config = get_config(bot_root)
    dockerfile = textwrap.dedent('''\
        FROM python:3
        RUN pip install zulip zulip-bots zulip-botserver
        ADD ./* bot/
        RUN pip install -r bot/requirements.txt
        ''')
    dockerfile += 'CMD [ "zulip-run-bot", "bot/{bot}", "-c", "bot/{zuliprc}" ]\n'.format(bot=config['bot'], zuliprc=config['zuliprc'])
    with open(bot_root + '/Dockerfile', "w") as file:
        file.write(dockerfile)

    bot_image = docker_client.images.build(path=bot_root, tag=bot_name)
    print(bot_image)

def start_bot(bot_name):
    containers = docker_client.containers.list()
    for container in containers:
        for tag in container.image.tags:
            if tag.startswith(bot_name.replace('@', '')):
                # Bot already running
                return False
    container = docker_client.containers.run(bot_name.replace('@', ''), detach=True)
    return True

def stop_bot(bot_name):
    containers = docker_client.containers.list()
    for container in containers:
        for tag in container.image.tags:
            if tag.startswith(bot_name.replace('@', '')):
                container.stop()
                return True
    return False
