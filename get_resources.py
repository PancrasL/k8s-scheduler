# coding:utf-8
from pprint import pprint
def printLine(char):
    print(char * 100)
from kubernetes import client, config
config.kube_config.load_kube_config("/root/.kube/config")

#获取API的CoreV1Api版本对象
v1 = client.CoreV1Api()

#列出 namespaces 
printLine("-")
print("list all namespaces:")
for ns in v1.list_namespace().items:
    print(ns.metadata.name)
printLine("-")

#列出所有的services
printLine("-")
print("list all services:")
ret = v1.list_service_for_all_namespaces(watch=False)
for i in ret.items:
    print("%s \t%s \t%s \t%s \t%s \n" % (i.kind, i.metadata.namespace, i.metadata.name, i.spec.cluster_ip, i.spec.ports ))
printLine("-")

#列出所有的pod
printLine("-")
print("list all pods:")
ret = v1.list_pod_for_all_namespaces(watch=False)
for i in ret.items:
    print("%s\t%s\t%s" % (i.status.pod_ip, i.metadata.namespace, i.metadata.name))
printLine("-")

#列出所有deploy
extV1Bete1 = client.ExtensionsV1beta1Api()
printLine("-")
print("list all deploys:")
ret = extV1Bete1.list_deployment_for_all_namespaces(watch=False)
pprint(ret.metadata)

printLine("-") 
##列出其他资源和以上类似，不懂可以查看(kubectl  api-resources)

