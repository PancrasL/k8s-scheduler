# coding:utf-8

import os, yaml, logging, copy

from kubernetes import client
from utils import convert_resource_unit


def load_exist_pod_resources_request():
    # key: pod_name value: {nodeName:nodeName, resources{}}
    exist_pod_resources_request = {}

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

    return exist_pod_resources_request


def load_node_available_resources():
    # key: node_name value: resources{}
    node_available_resources = {}

    api_core_v1 = client.CoreV1Api()

    ret_nodes = api_core_v1.list_node(watch=False)
    for item in ret_nodes.items:
        node_available_resources[item.metadata.name] = {
            "cpu": convert_resource_unit("cpu", item.status.allocatable["cpu"]),
            "memory": convert_resource_unit("memory", item.status.allocatable["memory"])
        }
    return node_available_resources


def load_node_allocatable_resources(node_available_resources, exist_pod_resources_request):
    #key: node_name value: resources{}
    node_allocatable_resources = {}  # node_available_resources-exist_pod_resources_request

    node_allocatable_resources = copy.deepcopy(node_available_resources)
    for exist_pod in exist_pod_resources_request:
        node_name = exist_pod_resources_request[exist_pod]["node_name"]
        node_allocatable_resources[node_name]["cpu"] -= exist_pod_resources_request[exist_pod]["resources"]["cpu_request"]
        node_allocatable_resources[node_name]["memory"] -= exist_pod_resources_request[exist_pod]["resources"]["memory_request"]

    return node_allocatable_resources


def load_pod_to_be_scheduled(tf_yaml_dir, cluster_index, exist_pod_resources_request):
    # key: pod_name value:meta_data
    pods_meta_data = {}
    # 保存描述任务的yaml文件路径
    pod_yaml_files = []
    #key: pod_name value: {resources{}}
    pod_to_be_scheduled = {}

    # 遍历所有的yaml文件
    for files in os.listdir(tf_yaml_dir + cluster_index):
        pod_yaml_files.append(tf_yaml_dir + cluster_index + '/' + files)

    for pod_yaml_file in pod_yaml_files:
        with open(os.path.join(os.path.dirname(__file__), pod_yaml_file)) as f:
            pod_meta_data = yaml.load(f, Loader=yaml.FullLoader)

            #pprint(pod_meta_data)
            pod_name = pod_meta_data["metadata"]["name"]
            pod_exist_flag = False
            for exist_pod in exist_pod_resources_request:
                if pod_name == exist_pod[:-6]:
                    pod_exist_flag = True
                    break
            if not pod_exist_flag:
                try:
                    pods_meta_data[pod_name] = pod_meta_data
                    containers = pod_meta_data["spec"]["template"]["spec"]["containers"]
                    all_container_in_pod_requests = {"cpu_request": 0, "memory_request": 0}
                    for container in containers:
                        try:
                            all_container_in_pod_requests["cpu_request"] += convert_resource_unit("cpu", container["resources"]["requests"]["cpu"])
                        #处理container中不含有request的问题
                        except Exception, e:
                            pass
                        try:
                            all_container_in_pod_requests["memory_request"] += convert_resource_unit("memory",
                                                                                                     container["resources"]["requests"]["memory"])
                        #处理container中不含有request的问题
                        except Exception, e:
                            pass
                    # 这里的pod_yaml_file指的是yaml文件的 file_path 路径
                    pod_to_be_scheduled[pod_name] = {"resources": all_container_in_pod_requests, "pod_yaml_file": pod_yaml_file}

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

    return pod_to_be_scheduled, pods_meta_data