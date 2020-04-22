# coding:utf-8

import sys, time
import logging
import subprocess

# 调度器的其他模块
import resource
import lock
from utils import convert_resource_unit, get_resources_list
from algorithm import determine_schedule_or_not, most_suitable_schedule, k8s_schedule, greedy_schedule, deploy_services
from shared_memory import shared_memory

# debug utils
from pprint import pprint

tf_cluster_dir = "/root/my_scheduler/jobs/"
#tf_job_dir = tf_cluster_dir + cluster_name
tf_job_dir = ""

# key: pod_name value: {nodeName:nodeName, resources{}}
exist_pod_resources_request = {}
# key: node_name value: resources{}
node_available_resources = {}
#key: node_name value: resources{}
node_allocatable_resources = {}  # node_available_resources-exist_pod_resources_request
#key: pod_name value: {resources{}}
# eg:{'tf-ps-1-2-0': {'pod_yaml_file': '/root/my_scheduler/temp_tests/tf_jobs/ps_pod0.yaml',
#                     'resources': {'cpu_request': 500.0,
#                                   'memory_request': 800000000.0}}
pod_to_be_scheduled = {}
# key: pod_name value:meta_data
pods_meta_data = {}
# key: service_name value:meta_data
services_meta_data = {}
# key: node_name value: resource_utilization
node_utilization = {}


#超卖
def overSale():
    global node_available_resources
    global node_utilization

    ret = subprocess.Popen("kubectl top node", shell=True, stdout=subprocess.PIPE)
    out = ret.stdout.readlines()
    out = out[1:]

    #获取节点资源使用率
    #超卖系数=(1-资源使用率)/2  资源使用率<80%
    #        =1                 资源使用率>=80%
    for line in out:
        resource_utilization = {"cpu_usage": 0, "cpu_utilization": 0, "memory_usage": 0, "memory_utilization": 0}  #单位分别为m, %, Mi, %
        splitLine = line.split()
        resource_utilization["cpu_usage"] = float(splitLine[1][:-1])
        resource_utilization["cpu_utilization"] = float(splitLine[2][:-1])
        resource_utilization["cpu_resource_coefficient"] = float((100 - resource_utilization["cpu_utilization"]) / 200) + 1

        resource_utilization["memory_usage"] = float(splitLine[3][:-2])
        resource_utilization["memory_utilization"] = float(splitLine[4][:-1])
        resource_utilization["memory_resource_coefficient"] = float((100 - resource_utilization["memory_utilization"]) / 200) + 1
        node_utilization[splitLine[0]] = resource_utilization

    for node in node_utilization:
        if node in node_available_resources:
            if (node_utilization[node]["cpu_utilization"] < 80):
                node_available_resources[node]["cpu"] = node_utilization[node]["cpu_resource_coefficient"] * node_available_resources[node]["cpu"]
            if (node_utilization[node]["memory_utilization"] < 80):
                node_available_resources[node][
                    "memory"] = node_utilization[node]["memory_resource_coefficient"] * node_available_resources[node]["memory"]
    pprint(node_available_resources)


#加载集群信息
def load_cluster_status():
    global exist_pod_resources_request
    global node_available_resources
    global node_allocatable_resources
    global pod_to_be_scheduled
    global pods_meta_data
    global services_meta_data
    # 获取集群内所有的pods的资源分配量
    exist_pod_resources_request = resource.load_exist_pod_resources_request()
    # pprint(exist_pod_resources_request)

    # 获取集群内所有的nodes总资源量
    node_available_resources = resource.load_node_available_resources()
    # pprint(node_available_resources)

    # 超卖
    overSale()

    # 扣除已分配的资源，计算剩余可分配资源
    node_allocatable_resources = resource.load_node_allocatable_resources(node_available_resources, exist_pod_resources_request)
    # pprint(node_allocatable_resources)

    # 获取待调度的pod
    pod_to_be_scheduled, pods_meta_data, services_meta_data = resource.load_pod_to_be_scheduled(tf_job_dir, exist_pod_resources_request)
    #pprint(pod_to_be_scheduled)


#集群调度
def schedule(schedule_model):
    if schedule_model == "kubernetes":
        k8s_schedule(tf_cluster_dir + cluster_name + '/')
    elif schedule_model == "greedy":
        deploy_services(services_meta_data)
        greedy_schedule()
    elif schedule_model == "suitable":
        deploy_services(services_meta_data)
        most_suitable_schedule(pods_meta_data, node_allocatable_resources, pod_to_be_scheduled, node_utilization)
    else:
        logging.error("unsupported schedule model!! Supported model: 'kubernetes' 'suitable' 'greedy'")


#集群资源不足以调度当前任务，则将该任务加入到待调度队列，待资源满足后，由monitor模块的守护进程进行调度
def add_to_reschedule_queue(schedule_model, yaml_file_path):
    global shared_memory

    to_be_scheduled_queue = shared_memory.get("to_be_scheduled_queue")
    if not to_be_scheduled_queue:
        to_be_scheduled_queue = []
    to_be_scheduled_pods = {
        "pods_yaml_file_path": yaml_file_path,
        "pods_requests": pod_to_be_scheduled,
        "cluster_name": cluster_name,
        "schedule_model": schedule_model
    }
    to_be_scheduled_queue.append(to_be_scheduled_pods)
    shared_memory.set("to_be_scheduled_queue", to_be_scheduled_queue)
    print("Add to to be scheduled queue:", yaml_file_path)


if __name__ == '__main__':
    #lock.finish_schedule()
    argvs = sys.argv
    pprint(argvs)
    if len(argvs) == 3:
        cluster_name = argvs[1]
        schedule_model = argvs[2]
    else:
        exit()

    tf_job_dir = tf_cluster_dir + cluster_name + '/'

    # 加锁
    lock.start_schedule()

    # 加载集群状态
    load_cluster_status()

    # 判断当前集群能否容纳待调度的tf集群
    pod_request_resources_list, node_allocatable_resources_list = get_resources_list(pod_to_be_scheduled, node_allocatable_resources)
    hashtable = {}
    determination = determine_schedule_or_not(0, pod_request_resources_list, node_allocatable_resources_list, hashtable)
    # 执行调度
    if determination:
        schedule(schedule_model)
    else:
        add_to_reschedule_queue(schedule_model, tf_job_dir)
    time.sleep(5)
    # 解锁
    lock.finish_schedule()
