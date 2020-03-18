# coding:utf-8

import sys
import logging
import string

# debug utils
from pprint import pprint

# kubernetes API
from kubernetes import client, config

tf_yaml_dir = "/root/my_scheduler/temp_tests/tf_jobs"


def load_cluster_status(cluster_index):
    # 集群认证
    config.load_kube_config("/root/.kube/config")

    # 获取集群内所有的pod
    api_core_v1 = client.CoreV1Api()

    # 用于部署Job类型的深度学习任务
    api_batch_v1 = client.BatchV1Api()

    ret_jobs = api_batch_v1.list_job_for_all_namespaces(watch=False)

    for items in ret_jobs.items:
        # 过滤掉已经结束运行的job
        if items.status.active == 1:
            # 使用dictionary保存pod请求的资源
            all_container_in_pod_requests = {
                "cpu_request": 0, "memory_request": 0}
            # 一个job中可能存在多个container
            for container in items.spec.template.spec.containers:
                try:
                    all_container_in_pod_requests["cpu_request"] += convert_resource_unit(
                        "cpu", container.resources.requests["cpu"])
                # 处理container中不含有request的问题
                except Exception, e:
                    pass
                try:
                    all_container_in_pod_requests["memory_request"] += convert_resource_unit(
                        "memory", container.resources.requests["memory"])
                # 处理container中不含有request的问题
                except Exception, e:
                    pass

    pprint(all_container_in_pod_requests)

# 单位的换算，由CPU转换成milliCPU，由Gi/Mi/Ki/G/M/K转化成Byte
def convert_resource_unit(resource_type, resource):
    flag = ""
    ret = 0
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
                "The CPU's configuration resource format is incorrect!!!")
            return 0
        return ret

    elif resource_type == "memory":
        if resource[-2:] == "Gi" or resource[-2:] == "Mi" or resource[-2:] == "Ki":
            if resource[-2:] == "Gi":
                flag = "Gi"
            elif resource[-2:] == "Mi":
                flag = "Mi"
            elif resource[-2:] == "Ki":
                flag = "Ki"
            resource = resource[:-2]
        elif resource[-1] == "G" or resource[-1] == "M" or resource[-1] == "K":
            if resource[-1] == "G":
                flag = "G"
            elif resource[-1] == "M":
                flag = "M"
            elif resource[-1] == "K":
                flag = "K"
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
                "The Memory's configuration resource format is incorrect!!!")
            return 0
        return ret
    # Todo：添加对其他资源数量转换的支持
    else:
        logging.error("Unknown Resource Type!!! Return 0!!!")
        return 0


if __name__ == '__main__':
    argvs = sys.argv
    pprint(argvs)
    if len(argvs) == 3:
        cluster_index = argvs[1]
        schedule_model = argvs[2]

    # 加载集群状态
    load_cluster_status(0)
