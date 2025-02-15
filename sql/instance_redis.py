# -*- coding: utf-8 -*-
"""
@File    : instance_redis.py
@Time    : 2024/12/30 11:49 上午
@Author  : xxlaila
@Software: PyCharm
"""
import logging
import json
from django.contrib.auth.decorators import permission_required
from django.http import HttpResponse
from common.utils.extend_json_encoder import ExtendJSONEncoder
import time
from sql.engines import get_tencent_redis, get_tencent_dbbrain_engine, get_huawei_redis
from sql.utils.resource_group import user_instances
from sql.models import Instance

logger = logging.getLogger(__name__)

@permission_required('sql.menu_redis_analysis', raise_exception=True)
def redis_live_session_details(request):
    """redis会话详情"""
    instance_name = request.POST.get('instance_name')
    try:
        user_instances(request.user, db_type=["redis"]).get(instance_name=instance_name)
    except Exception:
        result = {"status": 1, "msg": "你所在组未关联该实例", "data": []}
        return HttpResponse(json.dumps(result), content_type="application/json")
    instance_info = Instance.objects.get(instance_name=instance_name)
    if instance_info.cloud == "Tencent" and instance_info.db_type == "redis":
        query_engine = get_tencent_dbbrain_engine(instance=instance_info)
        instanceinfo_list = query_engine.tencent_api_DescribeRedisProcessListRequest()
    elif instance_info.cloud == "Huawei" and instance_info.db_type == "redis":
        query_engine = get_huawei_redis(instance=instance_info)
        instanceinfo_list = query_engine.huawei_api_ListClients()
    else:
        instanceinfo_list = {}
    if "Error" in instanceinfo_list.get("Error", {}):
        error_code = instanceinfo_list["Error"].get("Code")
        error_message = instanceinfo_list["Error"].get("Message")
        if error_code == "InvalidParameterValue" and "Proxy版本较低" in error_message:
            rows = []  # 直接返回空列表
        else:
            # 其他错误处理
            rows = []
    else:
        rows = []
        if instanceinfo_list:
            for row in instanceinfo_list.get('Processes', []):
                rows.append(row)
            # 排序
            rows.sort(key=lambda x: x.get("ProxyId"), reverse=True)
            # 取前30行
            rows = rows[:30]
    result = {'status': 0, 'msg': 'ok', 'rows': rows}
    return HttpResponse(json.dumps(result, cls=ExtendJSONEncoder, bigint_as_string=True),
                        content_type='application/json')

@permission_required('sql.menu_redis_analysis', raise_exception=True)
def redis_instance_cpu_time(request):
    """实例cpu耗时"""
    instance_name = request.POST.get('instance_name')

    try:
        user_instances(request.user, db_type=["redis"]).get(instance_name=instance_name)
    except Exception:
        result = {"status": 1, "msg": "你所在组未关联该实例", "data": []}
        return HttpResponse(json.dumps(result), content_type="application/json")

    instance_info = Instance.objects.get(instance_name=instance_name)
    if instance_info.cloud == "Tencent" and instance_info.db_type == "redis":
        query_engine = get_tencent_redis(instance=instance_info)
        instanceinfo_list = query_engine.tencent_api_DescribeInstanceMonitorTopNCmdTook()
    else:
        instanceinfo_list = {}
    # 查询大key
    if instanceinfo_list:
        hotkey_list = instanceinfo_list["Data"]

        rows = []
        for row in hotkey_list:
            rows.append(row)
        # 排序
        rows.sort(key=lambda x: x["Took"], reverse=1)
        # 取前10行
        rows = rows[:10]
    else:
        rows = []
    result = {'status': 0, 'msg': 'ok', 'rows': rows}
    return HttpResponse(json.dumps(result, cls=ExtendJSONEncoder, bigint_as_string=True),
                        content_type='application/json')

def analysis_tencent_redis_instanceinfo(instance_info, result):
    items = result["InstanceSet"][0]
    row = {}
    rows = []
    row["instancetype"] = "主库"
    row["instancename"] = items["InstanceName"]
    row["ipaddress"] = items["WanIp"]
    redis_type = items["Type"]

    # 根据不同的Redis类型设置对应的版本描述
    if redis_type == 1:
        row["version"] = "Redis2.8集群版"
    elif redis_type == 2:
        row["version"] = "Redis 2.8 内存版（标准架构）"
    elif redis_type == 3:
        row["version"] = "CKV 3.2 内存版（标准架构）"
    elif redis_type == 4:
        row["version"] = "CKV 3.2 内存版（集群架构）"
    elif redis_type == 5:
        row["version"] = "Redis 2.8 内存版（单机）"
    elif redis_type == 6:
        row["version"] = "Redis 4.0 内存版（标准架构）"
    elif redis_type == 7:
        row["version"] = "Redis 4.0 内存版（集群架构）"
    elif redis_type == 8:
        row["version"] = "Redis 5.0 内存版（标准架构）"
    elif redis_type == 9:
        row["version"] = "Redis 5.0 内存版（集群架构）"
    elif redis_type == 15:
        row["version"] = "Redis 6.2 内存版（标准架构）"
    elif redis_type == 16:
        row["version"] = "Redis 6.2 内存版（集群架构）"
    elif redis_type == 17:
        row["version"] = "Redis 7.0 内存版（标准架构）"
    elif redis_type == 18:
        row["version"] = "Redis 7.0 内存版（集群架构）"
    else:
        row["version"] = "未知版本"  # 如果类型不在上述列表中，则标记为未知版本
    row["cpu"] = '1'
    row["memory"] = items["Size"]
    row["roinstancesnum"] = items["RedisReplicasNum"]
    row['cloud'] = instance_info.cloud
    row["db_type"] = instance_info.db_type

    rows.append(row)
    return  rows

@permission_required('sql.menu_redis_analysis', raise_exception=True)
def redis_instanceinfo(request):
    """redis实例信息"""
    instance_name = request.POST.get('instance_name')

    try:
        user_instances(request.user, db_type=["redis"]).get(instance_name=instance_name)
    except Exception:
        result = {"status": 1, "msg": "你所在组未关联该实例", "data": []}
        return HttpResponse(json.dumps(result), content_type="application/json")

    instance_info = Instance.objects.get(instance_name=instance_name)
    if instance_info.cloud == "Tencent" and instance_info.db_type == "redis":
        query_engine = get_tencent_redis(instance=instance_info)
        result = query_engine.tencent_api_DescribeInstances()
        rows = analysis_tencent_redis_instanceinfo(instance_info, result)
    elif instance_info.cloud == "Huawei" and instance_info.db_type == "redis":
        query_engine = get_huawei_redis(instance=instance_info)
        result = query_engine.huawei_api_ShowInstance()
        rows = []
    else:
        rows = []

    result = {'status': 0, 'msg': 'ok', 'rows': rows}
    return HttpResponse(json.dumps(result, cls=ExtendJSONEncoder, bigint_as_string=True),
                        content_type='application/json')

@permission_required('sql.menu_redis_analysis', raise_exception=True)
def redis_bigkey(request):
    """redis 大key"""
    instance_name = request.POST.get('instance_name')

    try:
        user_instances(request.user, db_type=["redis"]).get(instance_name=instance_name)
    except Exception:
        result = {"status": 1, "msg": "你所在组未关联该实例", "data": []}
        return HttpResponse(json.dumps(result), content_type="application/json")

    reqtime = time.strftime("%Y-%m-%d", time.localtime())
    # 通过api查询出实例id
    instance_info = Instance.objects.get(instance_name=instance_name)
    if instance_info.cloud == "Tencent" and instance_info.db_type == "redis":
        query_engine = get_tencent_dbbrain_engine(instance=instance_info)
        instanceinfo_list = query_engine.tencent_api_DescribeRedisTopBigKeys(reqtime)
    elif instance_info.cloud == "Huawei" and instance_info.db_type == "redis":
        query_engine = get_huawei_redis(instance=instance_info)
        instanceinfo_list = query_engine.huawei_api_ShowBigkeyScanTaskDetails(reqtime)
    else:
        instanceinfo_list = {}

    if instanceinfo_list["TopKeys"]:
    # 查询大key
        bigkey_list = instanceinfo_list["TopKeys"]

        rows = []
        for row in bigkey_list:
            rows.append(row)
        # 排序
        rows.sort(key=lambda x: x["Length"], reverse=1)
        # 取前10行
        rows = rows[:10]
    else:
        rows = []

    result = {'status': 0, 'msg': 'ok', 'rows': rows}
    return HttpResponse(json.dumps(result, cls=ExtendJSONEncoder, bigint_as_string=True),
                        content_type='application/json')


@permission_required('sql.menu_redis_analysis', raise_exception=True)
def redis_hotkey(request):
    """redis 热key"""
    instance_name = request.POST.get('instance_name')

    try:
        user_instances(request.user, db_type=["redis"]).get(instance_name=instance_name)
    except Exception:
        result = {"status": 1, "msg": "你所在组未关联该实例", "data": []}
        return HttpResponse(json.dumps(result), content_type="application/json")

    instance_info = Instance.objects.get(instance_name=instance_name)
    if instance_info.cloud == "Tencent" and instance_info.db_type == "redis":
        query_engine = get_tencent_redis(instance=instance_info)
        instanceinfo_list = query_engine.tencent_api_DescribeInstanceMonitorHotKey()
    elif instance_info.cloud == "Huawei" and instance_info.db_type == "redis":
        query_engine = get_huawei_redis(instance=instance_info)
        instanceinfo_list = query_engine.huawei_api_ShowHotkeyTaskDetails()
    else:
        instanceinfo_list = {}
    # 查询大key
    if instanceinfo_list:
        hotkey_list = instanceinfo_list["Data"]

        rows = []
        for row in hotkey_list:
            rows.append(row)
        # 排序
        rows.sort(key=lambda x: x["Count"], reverse=1)
        # 取前10行
        rows = rows[:10]
    else:
        rows = []
    result = {'status': 0, 'msg': 'ok', 'rows': rows}
    return HttpResponse(json.dumps(result, cls=ExtendJSONEncoder, bigint_as_string=True),
                        content_type='application/json')

@permission_required('sql.menu_redis_analysis', raise_exception=True)
def redis_slowlog(request):
    """redis 慢查询"""
    instance_name = request.POST.get('instance_name')
    try:
        user_instances(request.user, db_type=["redis"]).get(instance_name=instance_name)
    except Exception:
        result = {"status": 1, "msg": "你所在组未关联该实例", "data": []}
        return HttpResponse(json.dumps(result), content_type="application/json")
    instance_info = Instance.objects.get(instance_name=instance_name)
    if instance_info.cloud == "Tencent" and instance_info.db_type == "redis":
        query_engine = get_tencent_redis(instance=instance_info)
        instanceinfo_list = query_engine.tencent_api_DescribeSlowLog()
    elif instance_info.cloud == "Huawei" and instance_info.db_type == "redis":
        query_engine = get_huawei_redis(instance=instance_info)
        instanceinfo_list = query_engine.huawei_api_ListSlowlog()
    else:
        instanceinfo_list = {}
    # 查询大key
    if instanceinfo_list:
        slowlog_list = instanceinfo_list["InstanceSlowlogDetail"]
        count = instanceinfo_list["TotalCount"]
    else:
        slowlog_list = []
        count = 0
    rows = []
    for row in slowlog_list:
        rows.append(row)
    # 排序
    rows.sort(key=lambda x: x["Duration"], reverse=1)
    # 取前10行
    rows = rows[:40]
    result = {'status': 0, 'msg': 'ok', 'rows': rows, 'count': count}
    return HttpResponse(json.dumps(result, cls=ExtendJSONEncoder, bigint_as_string=True),
                        content_type='application/json')