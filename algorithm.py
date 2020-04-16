# coding:utf-8

import copy, sys, os
import yaml
import logging
from kubernetes import config, client

from utils import convert_resource_unit

# 判断整个集群的现有资源能不能运行新来的tf的所有pod，假如可以，再进行对集群的调度，如果不行，将yaml文件的位置存储到memcached数据库
# 需要注意的是，对于指定的tf集群而言，只有当所有的wk节点被调度之后，整个集群才能正常工作
# 这是一个对 多个二维背包问题的 求解，将每个node节点看成二维背包，分别为CPU资源和内存资源，对每个节点进行二维背包求解，假如所有解集的并集包括tf所有节点，则可以进行调度，否则不能
# todo:需要求全解的解集，使用暴力回溯法求解
def determine_schedule_or_not(kth, pod_request_resources_list, node_allocatable_resources_list, hashtable):
    flag = 0
    if (kth >= len(pod_request_resources_list)):
        return 1

    for i in range(len(node_allocatable_resources_list)):
        if node_allocatable_resources_list[i][0] >= pod_request_resources_list[kth][0] and node_allocatable_resources_list[i][
                1] >= pod_request_resources_list[kth][1]:
            hashtable[tuple(tuple(l1) for l1 in node_allocatable_resources_list)] = 1
            node_allocatable_resources_list[i][0] -= pod_request_resources_list[kth][0]
            node_allocatable_resources_list[i][1] -= pod_request_resources_list[kth][1]
            flag = determine_schedule_or_not(kth + 1, pod_request_resources_list, node_allocatable_resources_list, hashtable)
            node_allocatable_resources_list[i][0] += pod_request_resources_list[kth][0]
            node_allocatable_resources_list[i][1] += pod_request_resources_list[kth][1]
        else:
            hashtable[tuple(tuple(l1) for l1 in node_allocatable_resources_list)] = -1

    return flag


#最适资源调度策略
def most_suitable_schedule(pods_meta_data, node_allocatable_resources, pod_to_be_scheduled, node_utilization):
    #todo: need a better way to deal with pod_max_cpu=0 or pod_max_memory=0,because they are divisor
    pod_max_cpu = 0.000001
    pod_max_memory = 0.000001
    pod_cpu_ratio = 1 / 2.0
    pod_memory_ratio = 1 / 2.0

    #将cpu和memory的资源比例值相同
    node_cpu_ratio = 1 / 2.0
    node_memory_ratio = 1 / 2.0
    pod_to_be_scheduled_list = []
    pod_score = {}

    #以最大资源量为基准，以便将资源归'1'化处理
    for pod in pod_to_be_scheduled:
        if pod_to_be_scheduled[pod]["resources"]["cpu_request"] > pod_max_cpu:
            pod_max_cpu = pod_to_be_scheduled[pod]["resources"]["cpu_request"]
        if pod_to_be_scheduled[pod]["resources"]["memory_request"] > pod_max_memory:
            pod_max_memory = pod_to_be_scheduled[pod]["resources"]["memory_request"]

    for pod in pod_to_be_scheduled:
        pod_score[pod] = pod_to_be_scheduled[pod]["resources"]["cpu_request"] / pod_max_cpu * pod_cpu_ratio + pod_to_be_scheduled[pod]["resources"][
            "memory_request"] / pod_max_memory * pod_memory_ratio
    pod_score = sorted(pod_score.iteritems(), key=lambda dic: dic[1], reverse=False)

    #队列构成方式：首先是ps，之后是按资源需求升序的wk
    for pod in pod_score:
        #专门针对tensorflow框架
        if pod[0][:5] == "tf-ps":
            pod_to_be_scheduled_list.insert(0, pod[0])
        else:
            pod_to_be_scheduled_list.append(pod[0])

    print "pod_to_be_scheduled_list =", pod_to_be_scheduled_list

    #最佳匹配算法
    #考虑两种情况：1.没有可以完全容纳下所有pod的节点，需要做的是首先选取一个最大的节点(尽可能多地)将待创建pod列表前面的pod创建，之后再将剩余的pod选择合适的节点
    #2.直接存在多个可以容纳所有pod的节点，需要选择一个最接近所有pod使用资源的节点
    pod_packer = copy.deepcopy(pod_to_be_scheduled_list)
    #schedule method
    while pod_to_be_scheduled_list:
        remain_pod_cpu_request = 0
        remain_pod_memory_request = 0
        abundant_resource_node = {}

        # remain pods' resources request
        for pod in pod_packer:
            remain_pod_cpu_request += pod_to_be_scheduled[pod]["resources"]["cpu_request"]
            remain_pod_memory_request += pod_to_be_scheduled[pod]["resources"]["memory_request"]
        #筛选出资源充足的node
        for node in node_allocatable_resources:
            if remain_pod_cpu_request <= node_allocatable_resources[node]["cpu"] and remain_pod_memory_request <= node_allocatable_resources[node][
                    "memory"]:
                abundant_resource_node[node] = {
                    "remain_cpu": node_allocatable_resources[node]["cpu"] - remain_pod_cpu_request,
                    "remain_memory": node_allocatable_resources[node]["memory"] - remain_pod_memory_request
                }

        print "node_allocatable_resources =", node_allocatable_resources
        print "abundant_resource_node =", abundant_resource_node

        if abundant_resource_node:
            #todo: need a better way to deal with max_abundant_cpu=0 or max_abundant_memory=0,because they are divisor
            max_abundant_cpu = 0.000001
            max_abundant_memory = 0.000001
            resource_delta = {}

            #only if the abundant_resource_node>1 can we calculate the max cpu and memory value
            if len(abundant_resource_node) > 1:
                for node in abundant_resource_node:
                    if abundant_resource_node[node]["remain_cpu"] >= max_abundant_cpu:
                        max_abundant_cpu = abundant_resource_node[node]["remain_cpu"]
                    if abundant_resource_node[node]["remain_memory"] >= max_abundant_memory:
                        max_abundant_memory = abundant_resource_node[node]["remain_memory"]
                for node in abundant_resource_node:
                    resource_delta[node] = abundant_resource_node[node]["remain_cpu"] / max_abundant_cpu * node_cpu_ratio + abundant_resource_node[
                        node]["remain_memory"] / max_abundant_memory * node_memory_ratio
                # pod list in ascending order
                resource_delta = sorted(resource_delta.iteritems(), key=lambda dic: dic[1], reverse=False)
            #todo: need a better way to deal with only one node is satisfied with the if condition's case
            else:
                resource_delta = sorted(abundant_resource_node.iteritems(), key=lambda dic: dic[1], reverse=False)

            print "resource_delta =", resource_delta

            #选择差距最小的节点运行所有的pod
            dest_node = resource_delta[0][0]

            print "pod_packer =", pod_packer
            print "dest_node =", dest_node

            # python's magic，浅拷贝
            for pod in pod_packer[:]:
                binding_pod_to_node(dest_node, pods_meta_data[pod], node_utilization[dest_node])
                node_allocatable_resources[dest_node]["cpu"] -= pod_to_be_scheduled[pod]["resources"]["cpu_request"]
                node_allocatable_resources[dest_node]["memory"] -= pod_to_be_scheduled[pod]["resources"]["memory_request"]
                pod_to_be_scheduled_list.remove(pod)
            #剩下的pod重新执行上述流程
            pod_packer = copy.deepcopy(pod_to_be_scheduled_list)

            print "pod_packer =", pod_packer
            print "pod_to_be_scheduled_list=", pod_to_be_scheduled_list

        #现有节点资源不足以支撑运行所有的pod，将列表靠前的pod运行,直到找到最先支持最多pod运行的节点为止
        else:
            pod_packer = copy.deepcopy(pod_packer[:-1])

    print "Done......"


#贪心调度策略
def greedy_schedule():
    return


#k8s的默认调度策略
def k8s_schedule(yaml_dir):
    sys_ret = os.system("kubectl create -f " + yaml_dir)
    if sys_ret:
        logging.error("create pods " + yaml_dir + " failed!!! Can't create these pods!!!")
        sys.exit(2)
    # 等待一个文件夹中所有的job创建完成为止
    for yaml_file_str in os.listdir(yaml_dir):
        if "pod" in yaml_file_str:
            with open(yaml_dir + yaml_file_str) as f:
                yaml_description = yaml.load(f, Loader=yaml.FullLoader)
                #config.load_kube_config("/root/.kube/config")
                # 注意创建job对应的版本是BatchV1Api
                api_instance = client.BatchV1Api()
                while True:
                    resp = api_instance.read_namespaced_job(name=yaml_description["metadata"]["name"], namespace='default')
                    if resp.status.active == 1:
                        break


# 部署服务
def deploy_services(services_meta_data):
    api_core_v1 = client.CoreV1Api()
    for service in services_meta_data:
        api_core_v1.create_namespaced_service(body=services_meta_data[service], namespace="default")

# 将pod 调度到node上面，执行绑定过程
def binding_pod_to_node(node_name, pod_meta_data, resource_utilization = None):
    #config.load_kube_config("/root/.kube/config")
    #注意创建job对应的版本是BatchV1Api
    api_instance = client.BatchV1Api()
    #这里对于pod_meta_data不加上global，此处相当于在yaml文件中加入nodeName，指定调度到哪个节点
    pod_meta_data["spec"]["template"]["spec"]["nodeName"] = node_name

    #修改pod的request
    if resource_utilization:
        change_pod_request(pod_meta_data, resource_utilization)

    resp = api_instance.create_namespaced_job(body=pod_meta_data, namespace="default")

    #等待pod创建完毕再创建下一个pod，因为需要获取pod使用集群资源的情况才能对接下来的pod进行调度
    #todo: 有没有可能参考k8s中的assumedPod进行设计
    while True:
        resp = api_instance.read_namespaced_job(name=pod_meta_data["metadata"]["name"], namespace='default')
        if resp.status.active == 1:
            break
    print("Job created. status='%s'" % str(resp.status))

def change_pod_request(pod_meta_data, resource_utilization):
    for container in pod_meta_data["spec"]["template"]["spec"]["containers"]:
        new_cpu_requests = float(convert_resource_unit("cpu", container["resources"]["requests"]["cpu"])) / resource_utilization["cpu_resource_coefficient"]
        new_cpu_requests_str = str(int(new_cpu_requests))
        container["resources"]["requests"]["cpu"] = new_cpu_requests_str + "m"

        new_memory_requests = float(convert_resource_unit("memory", container["resources"]["requests"]["memory"])) / resource_utilization["memory_resource_coefficient"]
        new_memory_requests_str = str(int(new_memory_requests)/1000000)#单位转化为M
        container["resources"]["requests"]["memory"] = new_cpu_requests_str + "M"