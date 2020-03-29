# coding:utf-8

import sys

# 其他模块
import resource
from utils import convert_resource_unit, trans_dict_to_list
from algorithm import determine_schedule_or_not, most_suitable_schedule

# debug utils
from pprint import pprint

# kubernetes API
from kubernetes import client, config

tf_yaml_dir = "/root/my_scheduler/temp_tests/tf_jobs"

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
    pod_to_be_scheduled, pods_meta_data = resource.load_pod_to_be_scheduled(tf_yaml_dir, cluster_index, exist_pod_resources_request)
    pprint(pod_to_be_scheduled)


if __name__ == '__main__':
    argvs = sys.argv
    pprint(argvs)

    # 加载集群状态
    load_cluster_status("")

    # 判断当前集群能否容纳待调度的tf集群
    pod_list, node_allocatable_resources_list = trans_dict_to_list(pod_to_be_scheduled, node_allocatable_resources)
    #print "pod_list =", pod_list, "node_allocatable_resources_list =", node_allocatable_resources_list
    hashtable = {}
    determination = determine_schedule_or_not(0, pod_list, node_allocatable_resources_list, hashtable)
    #print "determination =", determination
    most_suitable_schedule(pods_meta_data, node_allocatable_resources, pod_to_be_scheduled)
