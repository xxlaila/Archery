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

    instance_info = Instance.objects.get(instance_name=instance_name)
    if instance_info.cloud == "Tencent" and instance_info.db_type == "mysql":
        query_engine = get_tencent_cdb_engine(instance=instance_info)
        instanceinfo_list = query_engine.tencent_api_DescribeDBInstances(
            instancetypes, instance_info.aliyunrdsconfig.rds_dbinstanceid)
    else:
        instanceinfo_list = {}

    rows = []
    roinstancesnum = 0
    # 提取需要的信息
    if instancetypes == 1:
        instancetype_str = "主库"
    elif instancetypes == 2:
        instancetype_str = "灾备"
    else:
        instancetype_str = "从库"
    if instanceinfo_list:
        for items in instanceinfo_list["Items"]:
            row = {}
            row["instancetype"] = instancetype_str
            row["instancename"] = items["InstanceName"]
            row["ipaddress"] = items["Vip"]
            row["version"] = items["EngineVersion"]
            row["cpu"] = items["Cpu"]
            row["memory"] = items["Memory"]
            row["volume"] = items["Volume"]
            for roitem in items["RoGroups"]:
                roinstances = roitem['RoInstances']
                roinstancesnum = roinstancesnum + len(roinstances)
            row["roinstancesnum"] = roinstancesnum
            rows.append(row)
    else:
        row = {}
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
    rows.extend(rows_master)
    rows.extend(rows_slave)
    print("查看行信息", rows)

    result = {'status': 0, 'msg': 'ok', 'rows': rows}
    return HttpResponse(json.dumps(result, cls=ExtendJSONEncoder, bigint_as_string=True),
                        content_type='application/json')
