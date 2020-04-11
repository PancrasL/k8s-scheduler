# coding:utf-8

import string
import logging


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
            logging.error("The CPU's configuration resource format is incorrect!!!" + e)
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
                ret *= 1024 * 1024 * 1024
            elif flag == "Mi":
                ret *= 1024 * 1024
            elif flag == "Ki":
                ret *= 1024
            elif flag == "G":
                ret *= 1000 * 1000 * 1000
            elif flag == "M":
                ret *= 1000 * 1000
            elif flag == "K":
                ret *= 1000
        except Exception, e:
            logging.error("The Memory's configuration resource format is incorrect!!!" + e)
            return 0
        return ret
    # Todo：添加对其他资源数量转换的支持
    else:
        logging.error("Unknown Resource Type!!! Return 0!!!")
        return 0


# 将字典变为列表
def get_resources_list(pod_to_be_scheduled, node_allocatable_resources):
    pod_list = []
    node_allocatable_resources_list = []
    for pod in pod_to_be_scheduled:
        # pod_list.append({"cpu_request": pod_to_be_scheduled[pod]["resources"]["cpu_request"], "memory_request":pod_to_be_scheduled[pod]["resources"]["memory_request"]})
        pod_list.append([pod_to_be_scheduled[pod]["resources"]["cpu_request"], pod_to_be_scheduled[pod]["resources"]["memory_request"]])
    for node in node_allocatable_resources:
        # node_allocatable_resources_list.append({"cpu": node_allocatable_resources[node]["cpu"], "memory": node_allocatable_resources[node]["memory"]})
        node_allocatable_resources_list.append([node_allocatable_resources[node]["cpu"], node_allocatable_resources[node]["memory"]])
    return pod_list, node_allocatable_resources_list
