# coding:utf-8
#采用共享内存实现锁操作
import time

from shared_memory import shared_memory


def start_schedule():
    while shared_memory.get("reschedule_flag"):
        # 等待重调度的过程执行完成
        print "reschedule_flag in shared memory =", shared_memory.get("reschedule_flag")
        time.sleep(2)
    # 将schedule_flag置成1，给重调度的进程判断，代表正在发生的调度这个过程正在执行
    # 模拟加锁
    shared_memory.set("schedule_flag", 1)


def finish_schedule():
    shared_memory.set("schedule_flag", 0)


def start_reschedule():
    while shared_memory.get("schedule_flag"):
        # 等待重调度的过程执行完成
        print "schedule_flag in shared memory =", shared_memory.get("schedule_flag")
        time.sleep(2)
    # 将schedule_flag置成1，给重调度的进程判断，代表正在发生的调度这个过程正在执行
    # 模拟加锁
    shared_memory.set("reschedule_flag", 1)


def finish_reschedule():
    shared_memory.set("reschedule_flag", 0)