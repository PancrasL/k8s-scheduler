# coding:utf-8

##利用memcache实现元数据数据库
import memcache

shared_memory = memcache.Client(['127.0.0.1:11211'], debug=0)