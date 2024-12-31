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
from sql.engines import get_tencent_redis, get_tencent_dbbrain_engine
from sql.utils.resource_group import user_instances
from sql.models import Instance

logger = logging.getLogger(__name__)


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
    else:
        result = {}

    items = result["InstanceSet"][0]
    row = {}
    rows = []
    row["instancetype"] = "主库"
    row["instancename"] = items["InstanceName"]
    row["ipaddress"] = items["WanIp"]
    redis_type = items["Type"]
    if redis_type == 1:
        row["version"] = "Redis2.8集群版"
    elif redis_type == 2:
        row["version"] = "Redis2.8主从版"
    elif redis_type == 6:
        row["version"] = "Redis4.0主从版"
    elif redis_type == 7:
        row["version"] = "Redis4.0集群版"
    elif redis_type == 8:
        row["version"] = "Redis5.0主从版"
    elif redis_type == 9:
        row["version"] = "Redis5.0集群版"
    else:
        row["version"] = "未知"
    row["cpu"] = '1'
    row["memory"] = items["Size"]
    row["roinstancesnum"] = items["RedisReplicasNum"]
    row['cloud'] = instance_info.cloud
    row["db_type"] = instance_info.db_type

    rows.append(row)

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
