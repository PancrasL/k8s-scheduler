# coding:utf-8

import sys
import logging
import requests
import string

# debug utils
from pprint import pprint

# kubernetes API
from kubernetes import client, config

tf_yaml_dir = "/root/my_scheduler/temp_tests/tf_jobs"

# key: pod_name value: {nodeName:nodeName, resources{}}
exist_pod_resources_request = {}


def load_cluster_status(cluster_index):
    global exist_pod_resources_request

    # 集群认证
    config.load_kube_config("/root/.kube/config")

    # API实例
    api_core_v1 = client.CoreV1Api()
    api_batch_v1 = client.BatchV1Api()

    # 获取集群内所有的pods
    ret_pods = api_core_v1.list_pod_for_all_namespaces(watch=False)
    for item in ret_pods.items:
        # 一个pod中的多个container是被封装成了一个list列表，需要遍历列表获取各个container的需要的资源
        all_container_in_pod_requests = {
            "cpu_request": 0, "memory_request": 0}
        for container in item.spec.containers:
            try:
                all_container_in_pod_requests["cpu_request"] += convert_resource_unit("cpu",
                                                                                      container.resources.requests[
                                                                                          "cpu"])
            # 处理container中不含有request的问题
            except Exception, e:
                pass
            try:
                all_container_in_pod_requests["memory_request"] += convert_resource_unit("memory",
                                                                                         container.resources.requests[
                                                                                             "memory"])
            # 处理container中不含有request的问题
            except Exception, e:
                pass

        try:
            exist_pod_resources_request[item.metadata.name] = {"node_name": item.spec.node_name,
                                                                    "resources": all_container_in_pod_requests}
        # 上面的语句在pod被删除之后，可能还会扫描到pod，此时requests返回的请求为None，所以会报错：KeyError: 'spec'
        # 既然pod都已经被杀死了，那么exist_pod_resources_request这个字典中本来就不应该出现这个pod，因此出现异常就不做任何处理
        except Exception, e:
            pass
    pprint(exist_pod_resources_request)
    # 获取集群内所有的nodes
    ret_nodes = api_core_v1.list_node(watch=False)

    pass
# 单位的换算，由CPU转换成milliCPU，由Gi/Mi/Ki/G/M/K转化成Byte


def convert_resource_unit(resource_type, resource):
    flag = ""
    ret = 0
    # CPU资源
    if resource_type == "cpu":
        if resource[-1] == "m":
            resource = resource[:-1]
            flag = "milli"
        try:
            ret = string.atof(resource)
            if flag == "":
                ret *= 1000
        except Exception, e:
            logging.error(
                "The CPU's configuration resource format is incorrect!!!" + e)
            return 0
        return ret

    # 内存资源
    elif resource_type == "memory":
        if resource[-2:] == "Gi" or resource[-2:] == "Mi" or resource[-2:] == "Ki":
            flag = resource[-2:]
            resource = resource[:-2]
        elif resource[-1] == "G" or resource[-1] == "M" or resource[-1] == "K":
            flag = resource[-1]
            resource = resource[:-1]
        try:
            ret = string.atof(resource)
            if flag == "Gi":
                ret *= 1024*1024*1024
            elif flag == "Mi":
                ret *= 1024*1024
            elif flag == "Ki":
                ret *= 1024
            elif flag == "G":
                ret *= 1000*1000*1000
            elif flag == "M":
                ret *= 1000*1000
            elif flag == "K":
                ret *= 1000
        except Exception, e:
            logging.error(
                "The Memory's configuration resource format is incorrect!!!" + e)
            return 0
        return ret
    # Todo：添加对其他资源数量转换的支持
    else:
        logging.error("Unknown Resource Type!!! Return 0!!!")
        return 0


if __name__ == '__main__':
    argvs = sys.argv
    pprint(argvs)

    # 加载集群状态
    load_cluster_status(0)
