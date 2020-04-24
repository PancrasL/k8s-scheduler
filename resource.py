# coding:utf-8

import os, yaml, logging, copy, subprocess

from kubernetes import config, client
from utils import convert_resource_unit

config.load_kube_config()

def load_exist_pod_resources_request():
    # key: pod_name value: {nodeName:nodeName, resources{}}
    exist_pod_resources_request = {}

    api_core_v1 = client.CoreV1Api()
    ret_pods = api_core_v1.list_pod_for_all_namespaces(watch=False)
    for item in ret_pods.items:
        # 正常运行的pod
        if item.status.phase == "Running" or item.status.phase == "Pending":
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
            except Exception, e:
                pass
        # 异常的pod
        else:
            #print(item.metadata.name, item.status.phase)
            if item.status.phase == "Failed":
                api_core_v1.delete_namespaced_pod(item.metadata.name, item.metadata.namespace)

    return exist_pod_resources_request


def load_node_available_resources():
    # key: node_name value: resources{}
    node_available_resources = {}

    api_core_v1 = client.CoreV1Api()

    ret_nodes = api_core_v1.list_node(watch=False)
    for item in ret_nodes.items:
        if item.metadata.name != "k8s-mst" and item.status.conditions[3].status == 'True':
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
        if node_name != "k8s-mst":
            node_allocatable_resources[node_name]["cpu"] -= exist_pod_resources_request[exist_pod]["resources"]["cpu_request"]
            node_allocatable_resources[node_name]["memory"] -= exist_pod_resources_request[exist_pod]["resources"]["memory_request"]

    return node_allocatable_resources


def load_pod_to_be_scheduled(yaml_dir, exist_pod_resources_request):
    # key: pod_name value:meta_data
    pods_meta_data = {}
    # 保存描述任务的yaml文件路径
    pod_yaml_files = []
    #key: pod_name value: {resources{}}
    pod_to_be_scheduled = {}
    #key: service_name value: meta_data
    services_meta_data = {}

    api_core_v1 = client.CoreV1Api()
    # 遍历所有的yaml文件
    for files in os.listdir(yaml_dir):
        pod_yaml_files.append(yaml_dir + '/' + files)

    for pod_yaml_file in pod_yaml_files:
        with open(os.path.join(os.path.dirname(__file__), pod_yaml_file)) as f:
            pod_meta_data = yaml.load(f, Loader=yaml.FullLoader)
            pod_name = pod_meta_data["metadata"]["name"]
            pod_exist_flag = False

            for exist_pod in exist_pod_resources_request:
                if pod_name == exist_pod[:-6]:
                    pod_exist_flag = True
                    break

            if not pod_exist_flag:
                if (pod_meta_data["kind"] == "Service"):
                    try:
                        #api_core_v1.create_namespaced_service(body=pod_meta_data, namespace="default")
                        services_meta_data[pod_meta_data["metadata"]["name"]] = pod_meta_data
                    #service可能会被重复创建
                    except Exception, e:
                        pass
                else:
                    try:
                        pods_meta_data[pod_name] = pod_meta_data
                        containers = pod_meta_data["spec"]["template"]["spec"]["containers"]
                        all_container_in_pod_requests = {"cpu_request": 0, "memory_request": 0}
                        for container in containers:
                            try:
                                all_container_in_pod_requests["cpu_request"] += convert_resource_unit("cpu",
                                                                                                      container["resources"]["requests"]["cpu"])
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
                        print "---An Exception happened!!!---", e, pod_meta_data

    return pod_to_be_scheduled, pods_meta_data, services_meta_data


#超卖
def overSale(pods_meta_data, pod_to_be_scheduled, node_available_resources):
    #集群总资源量
    cluster_total_resources = {"cpu": 0.0, "memory": 0.0}
    #集群已使用资源量
    cluster_used_resources = {"cpu": 0.0, "memory": 0.0}
    #集群资源使用率
    resource_utilization = {"cpu": 0.0, "memory": 0.0}
    #集群超卖系数
    over_sale_coefficient = {"cpu": 1.0, "memory": 1.0}

    # 计算集群总资源量
    for node in node_available_resources:
        cluster_total_resources["cpu"] += node_available_resources[node]["cpu"]
        cluster_total_resources["memory"] += node_available_resources[node]["memory"]

    # 计算集群已使用资源量
    ret = subprocess.Popen("kubectl top node", shell=True, stdout=subprocess.PIPE)
    out = ret.stdout.readlines()
    out = out[1:]
    for line in out:
        splitLine = line.split()
        cluster_used_resources["cpu"] += float(splitLine[1][:-1])
        cluster_used_resources["memory"] += float(splitLine[3][:-2]) * 1000  #转换为字节

    # 计算集群资源使用率
    resource_utilization["cpu"] = cluster_used_resources["cpu"] / cluster_total_resources["cpu"]
    resource_utilization["memory"] = cluster_used_resources["memory"] / cluster_total_resources["memory"]

    #计算集群超卖系数
    #超卖系数=(1-资源使用率)/2  资源使用率<80%
    #        =1                 资源使用率>=80%
    if resource_utilization["cpu"] < 0.8:
        over_sale_coefficient["cpu"] = 1 + (1 - resource_utilization["cpu"]) / 2
    if resource_utilization["memory"] < 0.8:
        over_sale_coefficient["memory"] = 1 + (1 - resource_utilization["memory"]) / 2

    print "coefficient = ", over_sale_coefficient
    # 修改pod的request
    for pod in pods_meta_data:
        change_pod_request(pods_meta_data[pod], over_sale_coefficient)
    for pod in pod_to_be_scheduled:
        pod_to_be_scheduled[pod]["resources"]["cpu_request"] = pod_to_be_scheduled[pod]["resources"]["cpu_request"]/over_sale_coefficient["cpu"]
        pod_to_be_scheduled[pod]["resources"]["memory_request"] = pod_to_be_scheduled[pod]["resources"]["memory_request"]/over_sale_coefficient["memory"]


def change_pod_request(pod_meta_data, over_sale_coefficient):
    for container in pod_meta_data["spec"]["template"]["spec"]["containers"]:
        new_cpu_requests = float(convert_resource_unit("cpu",
                                                       container["resources"]["requests"]["cpu"])) / over_sale_coefficient["cpu"]
        new_cpu_requests_str = str(int(new_cpu_requests))
        container["resources"]["requests"]["cpu"] = new_cpu_requests_str + "m"

        new_memory_requests = float(convert_resource_unit(
            "memory", container["resources"]["requests"]["memory"])) / over_sale_coefficient["memory"]
        new_memory_requests_str = str(int(new_memory_requests) / 1000000)  #单位转化为M
        container["resources"]["requests"]["memory"] = new_cpu_requests_str + "M"