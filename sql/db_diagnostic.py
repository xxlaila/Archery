import logging
import traceback
import MySQLdb

# import simplejson as json
import json
from django.contrib.auth.decorators import permission_required

from django.http import HttpResponse

from sql.engines import get_engine, get_tencent_dbbrain_engine
from common.utils.extend_json_encoder import ExtendJSONEncoder, ExtendJSONEncoderBytes
from sql.utils.resource_group import user_instances
from .models import Instance


logger = logging.getLogger("default")


# 问题诊断--进程列表
@permission_required("sql.process_view", raise_exception=True)
def process(request):
    instance_name = request.POST.get("instance_name")
    command_type = request.POST.get("command_type")
    request_kwargs = {
        key: value for key, value in request.POST.items() if key != "command_type"
    }

    try:
        instance = user_instances(request.user).get(instance_name=instance_name)
    except Instance.DoesNotExist:
        result = {"status": 1, "msg": "你所在组未关联该实例", "data": []}
        return HttpResponse(json.dumps(result), content_type="application/json")
    if instance.cloud == "Aliyun" and instance.db_type == "mysql":
        query_engine = get_engine(instance=instance)
        query_result = query_engine.processlist(command_type=command_type, **request_kwargs)
    else:
        query_engine = get_tencent_dbbrain_engine(instance=instance)
        query_result = query_engine.tencent_api_DescribeMySqlProcessList()
    # processlist方法已提升为父类方法，简化此处的逻辑。进程添加新数据库支持时，改前端即可。
    if query_result:
        if hasattr(query_result, 'error') and not query_result.error:
            processlist = query_result.to_dict()
            result = {"status": 0, "msg": "ok", "rows": processlist}
        elif hasattr(query_result, 'error'):
            result = {"status": 1, "msg": query_result.error}
        else:
            processlist = query_result
            result = {"status": 0, "msg": "ok", "rows": processlist}
    else:
        result = {"status": 0, "msg": "ok", "rows": {}}

    # 返回查询结果
    # ExtendJSONEncoderBytes 使用json模块，bigint_as_string只支持simplejson
    return HttpResponse(
        json.dumps(result, cls=ExtendJSONEncoderBytes), content_type="application/json"
    )


# 问题诊断--通过线程id构建请求 这里只是用于确定将要kill的线程id还在运行
@permission_required("sql.process_kill", raise_exception=True)
def create_kill_session(request):
    instance_name = request.POST.get("instance_name")
    thread_ids = request.POST.get("ThreadIDs")

    try:
        instance = user_instances(request.user).get(instance_name=instance_name)
    except Instance.DoesNotExist:
        result = {"status": 1, "msg": "你所在组未关联该实例", "data": []}
        return HttpResponse(json.dumps(result), content_type="application/json")

    result = {"status": 0, "msg": "ok", "data": []}
    query_engine = get_engine(instance=instance)
    if instance.db_type == "mysql":
        if instance.cloud == "Aliyun":
            result["data"] = query_engine.get_kill_command(json.loads(thread_ids))
        else:
            query_engine = get_tencent_dbbrain_engine(instance=instance)
            result["data"] = query_engine.tencent_api_CreateKillTask(json.loads(thread_ids))
    elif instance.db_type == "mongo":
        kill_command = query_engine.get_kill_command(json.loads(thread_ids))
        result["data"] = kill_command
    elif instance.db_type == "oracle":
        result["data"] = query_engine.get_kill_command(json.loads(thread_ids))
    else:
        result = {
            "status": 1,
            "msg": "暂时不支持{}类型数据库通过进程id构建请求".format(instance.db_type),
            "data": [],
        }
        return HttpResponse(json.dumps(result), content_type="application/json")
    # 返回查询结果
    return HttpResponse(
        json.dumps(result, cls=ExtendJSONEncoder, bigint_as_string=True),
        content_type="application/json",
    )


# 问题诊断--终止会话 这里是实际执行kill的操作
@permission_required("sql.process_kill", raise_exception=True)
def kill_session(request):
    instance_name = request.POST.get("instance_name")
    thread_ids = request.POST.get("ThreadIDs")
    result = {"status": 0, "msg": "ok", "data": []}

    try:
        instance = user_instances(request.user).get(instance_name=instance_name)
    except Instance.DoesNotExist:
        result = {"status": 1, "msg": "你所在组未关联该实例", "data": []}
        return HttpResponse(json.dumps(result), content_type="application/json")

    engine = get_engine(instance=instance)
    r = None
    if instance.db_type == "mysql":
        if instance.cloud == "Aliyun":
            r = engine.kill(json.loads(thread_ids))
        else:
            query_engine = get_tencent_dbbrain_engine(instance=instance)
            r = query_engine.tencent_api_CreateKillTask(json.loads(thread_ids))
    elif instance.db_type == "mongo":
        r = engine.kill_op(json.loads(thread_ids))
    elif instance.db_type == "oracle":
        r = engine.kill_session(json.loads(thread_ids))
    else:
        result = {
            "status": 1,
            "msg": "暂时不支持{}类型数据库终止会话".format(instance.db_type),
            "data": [],
        }
        return HttpResponse(json.dumps(result), content_type="application/json")

    if r and r.error:
        result = {"status": 1, "msg": r.error, "data": []}
    # 返回查询结果
    return HttpResponse(
        json.dumps(result, cls=ExtendJSONEncoder, bigint_as_string=True),
        content_type="application/json",
    )


# 问题诊断--表空间信息
@permission_required("sql.tablespace_view", raise_exception=True)
def tablespace(request):
    instance_name = request.POST.get("instance_name")
    offset = int(request.POST.get("offset", 0))
    limit = int(request.POST.get("limit", 14))
    try:
        instance = user_instances(request.user).get(instance_name=instance_name)
    except Instance.DoesNotExist:
        result = {"status": 1, "msg": "你所在组未关联该实例", "data": []}
        return HttpResponse(json.dumps(result), content_type="application/json")

    if instance.db_type in ["mysql", "oracle"]:
        if instance.cloud == "Aliyun":
            query_engine = get_engine(instance=instance)
        else:
            query_engine = get_tencent_dbbrain_engine(instance=instance)
        query_result = query_engine.tablespace(offset, limit)

    else:
        result = {
            "status": 1,
            "msg": "暂时不支持{}类型数据库的表空间信息查询".format(instance.db_type),
            "data": [],
        }
        return HttpResponse(json.dumps(result), content_type="application/json")

    if query_result:
        if isinstance(query_result, list):
            table_space = query_result
            total = len(table_space)
            result = {"status": 0, "msg": "ok", "rows": table_space, "total": total}
        elif not query_result.error:
            table_space = query_result.to_dict()
            r = query_engine.tablespace_count()
            total = r.rows[0][0]
            result = {"status": 0, "msg": "ok", "rows": table_space, "total": total}
        else:
            result = {"status": 1, "msg": query_result.error}
    else:
        result = {"status": 1, "msg": "查询结果为空", "data": []}
    # 返回查询结果
    return HttpResponse(
        json.dumps(result, cls=ExtendJSONEncoder, bigint_as_string=True),
        content_type="application/json",
    )


# 问题诊断--锁等待
@permission_required("sql.trxandlocks_view", raise_exception=True)
def trxandlocks(request):
    instance_name = request.POST.get("instance_name")

    try:
        instance = user_instances(request.user).get(instance_name=instance_name)
    except Instance.DoesNotExist:
        result = {"status": 1, "msg": "你所在组未关联该实例", "data": []}
        return HttpResponse(json.dumps(result), content_type="application/json")
    if instance.cloud == "Aliyun":
        query_engine = get_engine(instance=instance)
    else:
        query_engine = get_tencent_dbbrain_engine(instance=instance)
    if instance.db_type == "mysql":
        query_result = query_engine.trxandlocks()
    elif instance.db_type == "oracle":
        query_result = query_engine.lock_info()
    else:
        result = {
            "status": 1,
            "msg": "暂时不支持{}类型数据库的锁等待查询".format(instance.db_type),
            "data": [],
        }
        return HttpResponse(json.dumps(result), content_type="application/json")

    if not query_result.error:
        trxandlocks = query_result.to_dict()
        result = {"status": 0, "msg": "ok", "rows": trxandlocks}
    else:
        result = {"status": 1, "msg": query_result.error}

    # 返回查询结果
    return HttpResponse(
        json.dumps(result, cls=ExtendJSONEncoder, bigint_as_string=True),
        content_type="application/json",
    )


# 问题诊断--长事务
@permission_required("sql.trx_view", raise_exception=True)
def innodb_trx(request):
    instance_name = request.POST.get("instance_name")

    try:
        instance = user_instances(request.user).get(instance_name=instance_name)
    except Instance.DoesNotExist:
        result = {"status": 1, "msg": "你所在组未关联该实例", "data": []}
        return HttpResponse(json.dumps(result), content_type="application/json")
    if instance.cloud == "Aliyun":
        query_engine = get_engine(instance=instance)
    else:
        query_engine = get_tencent_dbbrain_engine(instance=instance)
    if instance.db_type == "mysql":
        query_result = query_engine.get_long_transaction()
    else:
        result = {
            "status": 1,
            "msg": "暂时不支持{}类型数据库的长事务查询".format(instance.db_type),
            "data": [],
        }
        return HttpResponse(json.dumps(result), content_type="application/json")

    if not query_result.error:
        trx = query_result.to_dict()
        result = {"status": 0, "msg": "ok", "rows": trx}
    else:
        result = {"status": 1, "msg": query_result.error}

    # 返回查询结果
    return HttpResponse(
        json.dumps(result, cls=ExtendJSONEncoder, bigint_as_string=True),
        content_type="application/json",
    )
