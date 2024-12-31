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
from sql.engines import get_tencent_cdb_engine
from sql.utils.resource_group import user_instances
from sql.models import Instance

logger = logging.getLogger(__name__)

def extract_instanceinfo(instance_name, instancetypes):
    """提取实例具体信息"""

    try:
        instance_info = Instance.objects.get(instance_name=instance_name)
    except Instance.DoesNotExist:
        return []
    except Instance.MultipleObjectsReturned:
        return []

    if instance_info.cloud == "Tencent" and instance_info.db_type == "mysql":
        try:
            query_engine = get_tencent_cdb_engine(instance=instance_info)
            instanceinfo_list = query_engine.tencent_api_DescribeDBInstances(
                instancetypes,
                instance_info.aliyunrdsconfig.rds_dbinstanceid if hasattr(instance_info, 'aliyunrdsconfig') else None)
        except Exception as e:
            # 记录日志并返回空列表
            print(f"Error calling tencent_api_DescribeDBInstances: {e}")
            return []
    else:
        instanceinfo_list = {}

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
                })
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
