# coding:utf-8

import memcache
import time


def start_schedule(shared_memory):
    while shared_memory.get("reschedule_flag"):
        # 等待重调度的过程执行完成
        print "reschedule_flag in shared memory =", shared_memory.get("reschedule_flag")
        time.sleep(2)
    # 将schedule_flag置成1，给重调度的进程判断，代表正在发生的调度这个过程正在执行
    # 模拟加锁
    shared_memory.set("schedule_flag", 1)

def finish_schedule(shared_memory):
    shared_memory.set("schedule_flag", 0)