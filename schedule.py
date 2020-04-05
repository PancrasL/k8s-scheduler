# coding:utf-8

import sys
import memcache
import logging

# 其他模块
import resource
import lock
from utils import convert_resource_unit, get_resources_list
from algorithm import determine_schedule_or_not, most_suitable_schedule, k8s_schedule, greedy_schedule

# debug utils
from pprint import pprint

# kubernetes API
from kubernetes import client, config

tf_yaml_dir = "/root/my_scheduler/jobs/"

# 连接到memcache服务器
shared_memory = memcache.Client(['127.0.0.1:11211'], debug=0)

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


#加载集群信息
def load_cluster_status(cluster_index):
    global exist_pod_resources_request
    global node_available_resources
    global node_allocatable_resources
    global pod_to_be_scheduled
    global pods_meta_data

    # 集群认证
    config.load_kube_config("/root/.kube/config")

    # 获取集群内所有的pods的资源分配量
    exist_pod_resources_request = resource.load_exist_pod_resources_request()
    # pprint(exist_pod_resources_request)

    # 获取集群内所有的nodes总资源量
    node_available_resources = resource.load_node_available_resources()
    # pprint(node_available_resources)

    # 扣除已分配的资源，计算剩余可分配资源
    node_allocatable_resources = resource.load_node_allocatable_resources(node_available_resources, exist_pod_resources_request)
    # pprint(node_allocatable_resources)

    # 获取待调度的pod
    pod_to_be_scheduled, pods_meta_data = resource.load_pod_to_be_scheduled(tf_yaml_dir + cluster_index, exist_pod_resources_request)

    #pprint(pod_to_be_scheduled)


#集群调度
def schedule(schedule_model):
    if schedule_model == "kubernetes":
        k8s_schedule(tf_yaml_dir + cluster_index + '/')
    elif schedule_model == "greedy":
        greedy_schedule()
    elif schedule_model == "suitable":
        most_suitable_schedule(pods_meta_data, node_allocatable_resources, pod_to_be_scheduled)
    else:
        logging.error("unsupported schedule model!! Supported model: 'kubernetes' 'suitable' 'greedy'")


#当前资源不足，将待调度任务加入到队列中
def add_to_reschedule_queue(schedule_model, yaml_file_path):
    global shared_memory

    to_be_scheduled_queue = shared_memory.get("to_be_scheduled_queue")
    if not to_be_scheduled_queue:
        to_be_scheduled_queue = []
    to_be_scheduled_pods = {
        "pods_yaml_file_path": yaml_file_path,
        "pods_requests": pod_to_be_scheduled,
        "cluster_index": cluster_index,
        "schedule_model": schedule_model
    }
    to_be_scheduled_queue.append(to_be_scheduled_pods)
    shared_memory.set("to_be_scheduled_queue", to_be_scheduled_queue)


if __name__ == '__main__':
    argvs = sys.argv
    pprint(argvs)

    cluster_index = "1"
    schedule_model = "suitable"

    # 加锁
    lock.start_schedule(shared_memory)

    # 加载集群状态
    load_cluster_status(cluster_index)

    # 判断当前集群能否容纳待调度的tf集群
    pod_request_resources_list, node_allocatable_resources_list = get_resources_list(pod_to_be_scheduled, node_allocatable_resources)
    #print "pod_request_resources_list =", pod_request_resources_list, "node_allocatable_resources_list =", node_allocatable_resources_list
    hashtable = {}
    determination = determine_schedule_or_not(0, pod_request_resources_list, node_allocatable_resources_list, hashtable)

    # 执行调度
    if determination:
        schedule(schedule_model)
    else:
        add_to_reschedule_queue(schedule_model, tf_yaml_dir + cluster_index + '/')

    # 主调度过程执行完成，将标志位置成0
    lock.finish_schedule(shared_memory)
