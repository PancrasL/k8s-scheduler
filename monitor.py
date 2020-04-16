#!/bin/python
# coding:utf-8

######################################################################################################################
# monitor在master端表现为一个后台daemon，守护进程
# monitor 负责实现 对处于排队状态下的ps 和 wk进行调度
# 以及根据当前集群状态将待调度的tf集群尽可能地调度到同一节点，并对销毁已完成的训练任务
######################################################################################################################
# 系统模块
import logging
import os
import signal
import sys
import threading
import time

# 调度器其余模块
from resource import *
from algorithm import determine_schedule_or_not
from schedule import tf_cluster_dir
from shared_memory import shared_memory
from utils import get_resources_list

training_dir = "/root/nfsFile/"

# 所有的资源（物理主机的资源）和pod的占用资源都是两个资源的加权和，都这么计算
cpu_ratio = 1.0
memory_ratio = 0.0


# 获取之后到来的tf集群
# to_be_scheduled_queue[0]结构：
# {
#     "pods_yaml_file_path": yaml_file_path,
#     "pods_requests": top,
#     "cluster_name": cluster_name,
#     "schedule_model": schedule_model
# }
def get_to_be_scheduled_queue():
    to_be_scheduled_queue = shared_memory.get("to_be_scheduled_queue")
    return to_be_scheduled_queue


# 判断集群资源是否满足待调度队列对首任务的需求
def determine_schedule_queued_tf(node_allocatable_resources, pod_to_be_scheduled):
    # 判断当前集群能否容纳待调度的tf集群
    pod_request_resources_list, node_allocatable_resources_list = get_resources_list(pod_to_be_scheduled, node_allocatable_resources)
    hashtable = {}
    determination = determine_schedule_or_not(0, pod_request_resources_list, node_allocatable_resources_list, hashtable)
    return determination


# 决定是否对排队队列中的任务进行调度的守护进程
def schedule_tf():
    while True:
        node_allocatable_resources = load_node_allocatable_resources(load_node_available_resources(), load_exist_pod_resources_request())
        to_be_scheduled_queue = get_to_be_scheduled_queue()
        
        # 有排队的tf集群队列
        if to_be_scheduled_queue:
            print(time.strftime('%Y-%m-%d %H:%M:%S',time.localtime(time.time())), "to_be_scheduled_queue:", len(to_be_scheduled_queue))
            top = to_be_scheduled_queue[0]
            determination = determine_schedule_queued_tf(node_allocatable_resources, top["pods_requests"])
            if determination:
                sys_ret = os.system("python schedule.py " + top["cluster_name"] + " " +
                                    top["schedule_model"])  # todo:这不就是和新调度来的tf集群等同处理吗，直接调用shell系统执行python指令
                if sys_ret:
                    logging.error("执行schedule.py失败...")
                # 调度完成将原来排队队列中的tf的删除
                del (to_be_scheduled_queue[0])
                shared_memory.set("to_be_scheduled_queue", to_be_scheduled_queue)
        # 周期是5秒
        time.sleep(5)


# 删除训练运行完的ps和wk，腾出集群的可用资源，并删除训练的文件夹
def delete_finished_job_pods():
    while True:
        all_finished_jobs = set()
        for file_str in os.listdir(training_dir):
            if "finish" in file_str:
                all_finished_jobs.add(file_str)
        print "all_finished_jobs =", all_finished_jobs

        for cluster_name in os.listdir(tf_cluster_dir):
            pod_file_dir = tf_cluster_dir + cluster_name
            is_running_state = False
            # 记录已经完成任务的文件
            finished_tf_wks = []

            # 匹配
            for pod_file in os.listdir(pod_file_dir):
                # todo:这里的文件名直接在程序中写死，找到比如"wk_pod23.yaml"的文件
                if "wk_pod" in pod_file and ".yaml" in pod_file:
                    pod_file = pod_file[6:-5]  # 切割下"wk_pod23.yaml"的文件，使其名字只剩下23
                    pod_file = "finish-tf-wk-" + cluster_name + "-" + pod_file

                    if pod_file not in all_finished_jobs:
                        is_running_state = True  #代表训练过程还在进行，不能删除
                        break
                    else:
                        finished_tf_wks.append(pod_file)

            ######################################################-------------------------------------------------##################################################
            # is_running_state = True        # fixme: to be deleted
            ######################################################-------------------------------------------------##################################################

            # tf集群任务已经运行结束，可以执行删除工作：删除training_data文件夹，删除finish-tf-wk-1-2的标志文件，最后删除pod实体
            tf_code_dir_prefix = "distribute-ML-demo-master-"
            if not is_running_state:
                ##删除已完成任务的文件和文件夹
                for pod_file in os.listdir(pod_file_dir):
                    if ".yaml" in pod_file and "pod" in pod_file:
                        if "ps_pod" in pod_file:
                            #删除training_data文件夹
                            tf_code_dir = training_dir + tf_code_dir_prefix + cluster_name
                            if (os.path.exists(tf_code_dir)):
                                os.system("rm -rf " + tf_code_dir)

                            #删除结束标志文件
                            for file in finished_tf_wks:
                                print "需要删除的无用文件为:", training_dir + file + "*"

                                #执行成功返回0
                                if os.system("rm -f " + training_dir + file + "*"):
                                    logging.error("delete file " + training_dir + file + " failed!!!")
                                else:
                                    all_finished_jobs.remove(file)

                            print "更新all_finished_jobs =", all_finished_jobs

                ##删除已完成任务的pod
                for pod_file in os.listdir(pod_file_dir):
                    if ".yaml" in pod_file:
                        sys_ret = os.system("kubectl delete -f " + pod_file_dir + "/" + pod_file)
                        if sys_ret:
                            logging.error(pod_file + " 删除失败!!!")
        #每5s扫描一次
        time.sleep(5)


# 一个线程用于清理垃圾数据，一个线程用于监控是否可以进行重调度
def multi_threads():
    schedule_tf_thread = threading.Thread(target=schedule_tf, args=())
    delete_finished_job_pods_thread = threading.Thread(target=delete_finished_job_pods, args=())

    schedule_tf_thread.start()
    delete_finished_job_pods_thread.start()

    schedule_tf_thread.join()
    delete_finished_job_pods_thread.join()


# 按下Control+C即可杀死所有线程
class Watcher():

    def __init__(self):
        self.child = os.fork()
        if self.child == 0:
            return
        else:
            self.watch()

    def watch(self):
        try:
            os.wait()
        except KeyboardInterrupt:
            self.kill()
        sys.exit()

    def kill(self):
        try:
            os.kill(self.child, signal.SIGKILL)
        except OSError:
            pass


if __name__ == '__main__':
    #清空memcache
    shared_memory.flush_all()

    # 按下Ctrl+C杀死所有线程
    Watcher()

    # 开启两个线程
    multi_threads()
