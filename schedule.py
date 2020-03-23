# coding:utf-8

import sys
import logging
import requests
import string
import copy
import os
from os import path
import yaml

# 其他模块
from utils import convert_resource_unit

# debug utils
from pprint import pprint

# kubernetes API
from kubernetes import client, config

tf_yaml_dir = "/root/my_scheduler/temp_tests/tf_jobs"

# 保存描述任务的yaml文件路径
pod_yaml_files=[]

# key: pod_name value:meta_data
pods_meta_data={}
# key: pod_name value: {nodeName:nodeName, resources{}}
exist_pod_resources_request = {}
# key: node_name value: resources{}
node_available_resources = {}
#key: node_name value: resources{}
node_allocatable_resources={}   # node_available_resources-exist_pod_resources_request
#key: pod_name value: {resources{}}
# eg:'tf-ps-1-2-0': {'pod_yaml_file': 'xxx', 'resources': {'memory_request': xxx, 'cpu_request': xxx}}
pod_to_be_scheduled={}

def load_cluster_status(cluster_index):
    # 集群认证
    config.load_kube_config("/root/.kube/config")

    # 获取集群内所有的pods的资源分配量
    load_exist_pod_resources_request()
    # pprint(exist_pod_resources_request)

    # 获取集群内所有的nodes总资源量
    load_node_available_resources()
    # pprint(node_available_resources)

    # 扣除已分配的资源，计算剩余可分配资源
    load_node_allocatable_resources()
    # pprint(node_allocatable_resources)
    
    # 获取待调度的pod
    load_pod_to_be_scheduled(cluster_index)
    # pprint(pod_to_be_scheduled)                

def load_exist_pod_resources_request():
    global exist_pod_resources_request

    api_core_v1 = client.CoreV1Api()
    ret_pods = api_core_v1.list_pod_for_all_namespaces(watch=False)
    for item in ret_pods.items:
        # 正常运行的pod
        if item.status.phase == "Running":
            # 一个pod中的多个container是被封装成了一个list列表，需要遍历列表获取各个container的需要的资源
            all_container_in_pod_requests = {"cpu_request": 0, "memory_request": 0}
            for container in item.spec.containers:
                try:
                    all_container_in_pod_requests["cpu_request"] += convert_resource_unit("cpu", container.resources.requests["cpu"])
                # 处理container中不含有request的问题
                except Exception, e:
                    pass
                try:
                    all_container_in_pod_requests["memory_request"] += convert_resource_unit("memory", container.resources.requests["memory"])
                # 处理container中不含有request的问题
                except Exception, e:
                    pass

            try:
                exist_pod_resources_request[item.metadata.name] = {"node_name": item.spec.node_name, "resources": all_container_in_pod_requests}
            # 上面的语句在pod被删除之后，可能还会扫描到pod，此时requests返回的请求为None，所以会报错：KeyError: 'spec'
            # 既然pod都已经被杀死了，那么exist_pod_resources_request这个字典中本来就不应该出现这个pod，因此出现异常就不做任何处理
            except Exception, e:
                pass
        # 异常的pod
        else:
            logging.error(item.metadata.name, item.status.phase, "pod " + item.metadata.name + " is deleted")
            # api_core_v1.delete_namespaced_pod(item.metadata.name, item.metadata.namespace)

def load_node_available_resources():
    global node_available_resources

    api_core_v1 = client.CoreV1Api()

    ret_nodes = api_core_v1.list_node(watch=False)
    for item in ret_nodes.items:
        node_available_resources[item.metadata.name] = {
            "cpu": convert_resource_unit("cpu", item.status.allocatable["cpu"]),
            "memory": convert_resource_unit("memory", item.status.allocatable["memory"])
        }

def load_node_allocatable_resources():
    global node_allocatable_resources
    global node_available_resources

    node_allocatable_resources = copy.deepcopy(node_available_resources)
    for exist_pod in exist_pod_resources_request:
        node_name = exist_pod_resources_request[exist_pod]["node_name"]
        node_allocatable_resources[node_name]["cpu"] -= exist_pod_resources_request[exist_pod]["resources"]["cpu_request"]
        node_allocatable_resources[node_name]["memory"] -= exist_pod_resources_request[exist_pod]["resources"]["memory_request"]

def load_pod_to_be_scheduled(cluster_index):
    global pods_meta_data
    global pod_yaml_files
    global pod_to_be_scheduled
    global tf_yaml_dir
    # 遍历所有的yaml文件
    for files in os.listdir(tf_yaml_dir+cluster_index):
        pod_yaml_files.append(tf_yaml_dir+cluster_index+'/'+files)
    
    for pod_yaml_file in pod_yaml_files:
        with open(path.join(path.dirname(__file__), pod_yaml_file)) as f:
            pod_meta_data = yaml.load(f, Loader=yaml.FullLoader)
            
            #pprint(pod_meta_data)
            pod_name=pod_meta_data["metadata"]["name"]
            pod_exist_flag = False
            for exist_pod in exist_pod_resources_request:
                if pod_name == exist_pod[:-6]:
                    pod_exist_flag = True
                    break
            if not pod_exist_flag:
                try:
                    pods_meta_data[pod_name] = pod_meta_data
                    containers = pod_meta_data["spec"]["template"]["spec"]["containers"]
                    all_container_in_pod_requests={"cpu_request":0, "memory_request":0}
                    for container in containers:
                        try:
                            all_container_in_pod_requests["cpu_request"]+=convert_resource_unit("cpu", container["resources"]["requests"]["cpu"])
                        #处理container中不含有request的问题
                        except Exception, e:
                            pass
                        try:
                            all_container_in_pod_requests["memory_request"]+=convert_resource_unit("memory", container["resources"]["requests"]["memory"])
                        #处理container中不含有request的问题
                        except Exception, e:
                            pass
                    # 这里的pod_yaml_file指的是yaml文件的 file_path 路径
                    pod_to_be_scheduled[pod_name]={"resources": all_container_in_pod_requests, "pod_yaml_file": pod_yaml_file}

                #service 类型的yaml文件，同样需要创建
                except Exception, e:
                    print "---An Exception happened!!!---", e
                    # 可能会出现service已经被创建，但是重新创建的情况，因此需要try环绕一下
                    try:
                        print ""
                        #pprint(pod_meta_data)
                        #api_instance.create_namespaced_service(body=pod_meta_data, namespace="default")
                    except Exception, e:
                        pass 

if __name__ == '__main__':
    argvs = sys.argv
    pprint(argvs)

    # 加载集群状态
    load_cluster_status("")

    # # 判断当前集群能否容纳下调度来的tf集群
    # pod_list, node_allocatable_resources_list = pre_process(pod_to_be_scheduled, node_allocatable_resources)
    # #print "pod_list =", pod_list, "node_allocatable_resources_list =", node_allocatable_resources_list
    # hashtable = {}
    # determination = determine_schedule_or_not(0, pod_list, node_allocatable_resources_list, hashtable)
    # #print "determination =", determination

    # most_suitable_schedule()
