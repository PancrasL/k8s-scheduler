# coding=utf-8
from os import path
import yaml
from kubernetes import client, config
from pprint import pprint

config.load_kube_config()
print('-'*100)
f = open(path.join(path.dirname(__file__), "/tmp/deploy/myweb-deploy.yaml"))
api_instance = client.ExtensionsV1beta1Api()
namespace = 'default'
body = yaml.load(f)

api_response = api_instance.create_namespaced_deployment(namespace, body)

print('-'*100)
pprint(api_response)
