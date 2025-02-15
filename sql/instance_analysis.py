# -*- coding: utf-8 -*-
"""
@File    : instance_analysis.py
@Time    : 2024/12/30 2:10 下午
@Author  : xxlaila
@Software: PyCharm
"""
import logging
import json
from django.contrib.auth.decorators import permission_required
from django.http import HttpResponse
from common.utils.extend_json_encoder import ExtendJSONEncoder
import time
from sql.engines import get_tencent_cdb_engine, get_huawei_rds_engine
from sql.utils.resource_group import user_instances
from sql.models import Instance
from sql.models import AliyunRdsConfig

logger = logging.getLogger(__name__)

def analysis_tencent_data(instance_info, instanceinfo_list, instancetypes):
    """解析腾讯云数据"""
    rows = []
    instancetype_map = {
        1: "主库",
        2: "灾备",
        3: "从库",
    }
    instancetype_str = instancetype_map.get(instancetypes, "未知类型")
    items = instanceinfo_list.get("Items", [])
    if not items:
        return rows
    for item in items:
        rows.append({
            "instanceid": item.get("InstanceId", ""),
            "instancetype": instancetype_str,
            "instancename": item.get("InstanceName", ""),
            "ipaddress": item.get("Vip", ""),
            "version": item.get("EngineVersion", ""),
            "cpu": item.get("Cpu", 0),
            "memory": item.get("Memory", 0),
            "volume": item.get("Volume", 0),
            "qps": item.get("Qps", 0),
            "roinstancesnum": sum(len(group.get("RoInstances", [])) for group in item.get("RoGroups", [])),
            "cloud": instance_info.cloud,
            "db_type": instance_info.db_type
        })
        # 只读实例信息
        for rogroup in item.get("RoGroups", []):
            for roinstance in rogroup.get("RoInstances", []):
                rows.append({
                    "instanceid": rogroup.get("RoGroupId", ""),
                    "instancetype": "从库",
                    "instancename": roinstance.get("InstanceName", ""),
                    "ipaddress": roinstance.get("Vip", ""),
                    "version": roinstance.get("EngineVersion", ""),
                    "cpu": roinstance.get("Cpu", 0),
                    "memory": roinstance.get("Memory", 0),
                    "volume": roinstance.get("Volume", 0),
                    "qps": roinstance.get("Qps", 0),
                    "cloud": instance_info.cloud,
                    "db_type": instance_info.db_type
                })
    return rows

def analysis_huawei_data(instance_info, instanceinfo_list):
    """解析华为云数据"""
    rows = []
    instancetype_map = {
        "Single": "单机",
        "Ha": "主备",
        "Replica": "只读",
    }
    if not instanceinfo_list:
        return rows
    item = instanceinfo_list.instances
    # 添加主实例信息
    rows.append({
        "instanceid": item.instances.id,
        "instancetype": instancetype_map.get(item.type, "未知类型"),
        "instancename": item.name,
        "ipaddress": item.private_ips[0],
        "version": item.datastore['version'],
        "cpu": item.cpu,
        "memory": item.mem,
        "volume": item.volume.size,
        "qps": '',
        "roinstancesnum": sum(1 for instance in item.related_instance if instance.get("type") ==
                              "replica") if item.related_instance else 0,
        "cloud": instance_info.cloud,
        "db_type": instance_info.db_type
    })
    # 获取只读实例数量
    roinstancesnum = rows[0]["roinstancesnum"]
    if rows[0]['instancetype'] == "Ha" and roinstancesnum > 0:
        replica_ids = [instance["id"] for instance in item.related_instance if instance["type"] == "replica"]
        for replica_id in replica_ids:
            try:
                instance_info = (
                    AliyunRdsConfig.objects.filter(rds_dbinstanceid=replica_id).
                    select_related('instance').values_list('instance__instance_name', flat=True).first())
                qury_engine = get_huawei_rds_engine(instance=instance_info)
                instanceinfo_list = qury_engine.huawei_api_DescribeDBInstances(
                    instance_info.aliyunrdsconfig.rds_dbinstanceid if hasattr(instance_info,
                                                                              'aliyunrdsconfig') else None)
                infos = instanceinfo_list.instances
                rows.append({
                    "instanceid": infos.instances.id,
                    "instancetype": instancetype_map.get(item.type, "未知类型"),
                    "instancename": infos.name,
                    "ipaddress": infos.private_ips[0],
                    "version": item.datastore['version'],
                    "cpu": infos.cpu,
                    "memory": infos.mem,
                    "volume": infos.volume.size,
                    "qps": '',
                    "roinstancesnum": 0,
                    "cloud": instance_info.cloud,
                    "db_type": instance_info.db_type
                })
            except Exception as e:
                logger.error(f"Error retrieving read replica data: {e}")
    return rows

def extract_instanceinfo(instance_name, instancetypes):
    """提取实例具体信息"""

    try:
        instance_info = Instance.objects.get(instance_name=instance_name)
    except Instance.DoesNotExist:
        return []
    except Instance.MultipleObjectsReturned:
        return []
    rds_instance_id = (
        instance_info.aliyunrdsconfig.rds_dbinstanceid
        if hasattr(instance_info, 'aliyunrdsconfig') else None
    )
    try:
        if instance_info.cloud == "Tencent" and instance_info.db_type == "mysql":
            query_engine = get_tencent_cdb_engine(instance=instance_info)
            instanceinfo_list = query_engine.tencent_api_DescribeDBInstances(
                instancetypes, rds_instance_id)
            rows = analysis_tencent_data(instance_info, instanceinfo_list, instancetypes)
        elif instance_info.cloud == "Huawei" and instance_info.db_type == "mysql":
            qury_engine = get_huawei_rds_engine(instance=instance_info)
            instanceinfo_list = qury_engine.huawei_api_DescribeDBInstances()
            rows = analysis_huawei_data(instance_info, instanceinfo_list)
        else:
            rows = []
    except Exception as e:
        logger.error(f"Error retrieving instance info: {e}")
        return []
    return rows

@permission_required('sql.menu_instance_analysis', raise_exception=True)
def instanceinfo(request):
    """mysql 实例信息"""
    instance_name = request.POST.get('instance_name')

    try:
        user_instances(request.user, db_type=["mysql"]).get(instance_name=instance_name)
    except Exception:
        result = {"status": 1, "msg": "你所在组未关联该实例", "data": []}
        return HttpResponse(json.dumps(result), content_type="application/json")

    # 获取主从库信息
    rows_master = extract_instanceinfo(instance_name, 1)
    rows_slave = extract_instanceinfo(instance_name, 3)
    rows = []
    if rows_master:
        rows.extend(rows_master)
    if rows_slave:
        rows.extend(rows_slave)
        print("查看行信息", rows)
    result = {'status': 0, 'msg': 'ok', 'rows': rows}
    return HttpResponse(json.dumps(result, cls=ExtendJSONEncoder, bigint_as_string=True),
                        content_type='application/json')
