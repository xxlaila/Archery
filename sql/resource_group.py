# -*- coding: UTF-8 -*-
import logging
import traceback
from itertools import chain

import simplejson as json
from django.contrib.auth.models import Group
from django.db.models import F, Value, IntegerField
from django.http import HttpResponse
from common.utils.extend_json_encoder import ExtendJSONEncoder
from common.utils.permission import superuser_required
from common.utils.convert import Convert
from sql.models import ResourceGroup, Users, Instance, ResoueceGroupApply
from sql.utils.resource_group import user_instances, user_groups
from common.utils.const import WorkflowDict
from sql.utils.workflow_audit import Audit, AuditV2, AuditException
from django.contrib.auth.decorators import permission_required
from django.db.models import Q
from sql.notify import notify_for_audit
from django_q.tasks import async_task
from sql.utils.workflow_audit import get_auditor
from django.db import transaction
from common.utils.const import WorkflowStatus, WorkflowType, WorkflowAction
from django.shortcuts import render, get_object_or_404
from django.http import HttpResponseRedirect, FileResponse, Http404
from django.urls import reverse

logger = logging.getLogger(__name__)

@superuser_required
def group(request):
    """获取资源组列表"""
    limit = int(request.POST.get("limit"))
    offset = int(request.POST.get("offset"))
    limit = offset + limit
    search = request.POST.get("search", "")

    # 过滤搜索条件
    group_obj = ResourceGroup.objects.filter(group_name__icontains=search, is_deleted=0)
    group_count = group_obj.count()
    group_list = group_obj[offset:limit].values(
        "group_id", "group_name", "ding_webhook"
    )

    # QuerySet 序列化
    rows = [row for row in group_list]

    result = {"total": group_count, "rows": rows}
    # 返回查询结果
    return HttpResponse(
        json.dumps(result, cls=ExtendJSONEncoder, bigint_as_string=True),
        content_type="application/json",
    )


def associated_objects(request):
    """
    获取资源组已关联对象信息
    type：(0, '用户'), (1, '实例')
    """
    group_id = int(request.POST.get("group_id"))
    object_type = request.POST.get("type")
    limit = int(request.POST.get("limit"))
    offset = int(request.POST.get("offset"))
    limit = offset + limit
    search = request.POST.get("search")

    # 获取关联数据
    resource_group = ResourceGroup.objects.get(group_id=group_id)
    rows_users = resource_group.users_set.all()
    rows_instances = resource_group.instance_set.all()
    # 过滤搜索
    if search:
        rows_users = rows_users.filter(display__contains=search)
        rows_instances = rows_instances.filter(instance_name__contains=search)
    rows_users = rows_users.annotate(
        object_id=F("id"),
        object_type=Value(0, output_field=IntegerField()),
        object_name=F("display"),
        group_id=F("resource_group__group_id"),
        group_name=F("resource_group__group_name"),
    ).values("object_type", "object_id", "object_name", "group_id", "group_name")
    rows_instances = rows_instances.annotate(
        object_id=F("id"),
        object_type=Value(1, output_field=IntegerField()),
        object_name=F("instance_name"),
        group_id=F("resource_group__group_id"),
        group_name=F("resource_group__group_name"),
    ).values("object_type", "object_id", "object_name", "group_id", "group_name")
    # 过滤对象类型
    if object_type == "0":
        rows_obj = rows_users
        count = rows_obj.count()
        rows = [row for row in rows_obj][offset:limit]
    elif object_type == "1":
        rows_obj = rows_instances
        count = rows_obj.count()
        rows = [row for row in rows_obj][offset:limit]
    else:
        rows = list(chain(rows_users, rows_instances))
        count = len(rows)
        rows = rows[offset:limit]
    result = {"status": 0, "msg": "ok", "total": count, "rows": rows}
    return HttpResponse(
        json.dumps(result, cls=ExtendJSONEncoder), content_type="application/json"
    )


def unassociated_objects(request):
    """
    获取资源组未关联对象信息
    type：(0, '用户'), (1, '实例')
    """
    group_id = int(request.POST.get("group_id"))
    object_type = int(request.POST.get("object_type"))
    # 获取关联数据
    resource_group = ResourceGroup.objects.get(group_id=group_id)
    if object_type == 0:
        associated_user_ids = [user.id for user in resource_group.users_set.all()]
        rows = (
            Users.objects.exclude(pk__in=associated_user_ids)
            .annotate(object_id=F("pk"), object_name=F("display"))
            .values("object_id", "object_name")
        )
    elif object_type == 1:
        associated_instance_ids = [ins.id for ins in resource_group.instance_set.all()]
        rows = (
            Instance.objects.exclude(pk__in=associated_instance_ids)
            .annotate(object_id=F("pk"), object_name=F("instance_name"))
            .values("object_id", "object_name")
        )
    else:
        raise ValueError("关联对象类型不正确")

    rows = [row for row in rows]
    result = {"status": 0, "msg": "ok", "rows": rows, "total": len(rows)}
    return HttpResponse(json.dumps(result), content_type="application/json")


def instances(request):
    """获取资源组关联实例列表"""
    group_name = request.POST.get("group_name")
    group_id = ResourceGroup.objects.get(group_name=group_name).group_id
    tag_code = request.POST.get("tag_code")
    db_type = request.POST.get("db_type")

    # 先获取资源组关联所有实例列表
    ins = ResourceGroup.objects.get(group_id=group_id).instance_set.all()

    # 过滤项
    filter_dict = dict()
    # db_type
    if db_type:
        filter_dict["db_type"] = db_type
    if tag_code:
        filter_dict["instance_tag__tag_code"] = tag_code
        filter_dict["instance_tag__active"] = True
    ins = (
        ins.filter(**filter_dict)
        .order_by(Convert("instance_name", "gbk").asc())
        .values("id", "type", "db_type", "instance_name")
    )
    rows = [row for row in ins]
    result = {"status": 0, "msg": "ok", "data": rows}
    return HttpResponse(json.dumps(result), content_type="application/json")


def user_all_instances(request):
    """获取用户所有实例列表（通过资源组间接关联）"""
    user = request.user
    type = request.GET.get("type")
    db_type = request.GET.getlist("db_type[]")
    tag_codes = request.GET.getlist("tag_codes[]")
    instances = (
        user_instances(user, type, db_type, tag_codes)
        .order_by(Convert("instance_name", "gbk").asc())
        .values("id", "type", "db_type", "instance_name")
    )
    rows = [row for row in instances]
    result = {"status": 0, "msg": "ok", "data": rows}
    return HttpResponse(json.dumps(result), content_type="application/json")


@superuser_required
def addrelation(request):
    """
    添加资源组关联对象
    type：(0, '用户'), (1, '实例')
    """
    group_id = int(request.POST.get("group_id"))
    object_type = request.POST.get("object_type")
    object_list = json.loads(request.POST.get("object_info"))
    try:
        resource_group = ResourceGroup.objects.get(group_id=group_id)
        obj_ids = [int(obj.split(",")[0]) for obj in object_list]
        if object_type == "0":  # 用户
            resource_group.users_set.add(*Users.objects.filter(pk__in=obj_ids))
        elif object_type == "1":  # 实例
            resource_group.instance_set.add(*Instance.objects.filter(pk__in=obj_ids))
        result = {"status": 0, "msg": "ok"}
    except Exception as e:
        logger.error(traceback.format_exc())
        result = {"status": 1, "msg": str(e)}
    return HttpResponse(json.dumps(result), content_type="application/json")


def auditors(request):
    """获取资源组的审批流程"""
    group_name = request.POST.get("group_name")
    workflow_type = request.POST["workflow_type"]
    result = {
        "status": 0,
        "msg": "ok",
        "data": {"auditors": "", "auditors_display": ""},
    }
    if group_name:
        group_id = ResourceGroup.objects.get(group_name=group_name).group_id
        audit_auth_groups = Audit.settings(
            group_id=group_id, workflow_type=workflow_type
        )
    else:
        result["status"] = 1
        result["msg"] = "参数错误"
        return HttpResponse(json.dumps(result), content_type="application/json")

    # 获取权限组名称
    if audit_auth_groups:
        # 校验配置
        for auth_group_id in audit_auth_groups.split(","):
            try:
                Group.objects.get(id=auth_group_id)
            except Exception:
                result["status"] = 1
                result["msg"] = "审批流程权限组不存在，请重新配置！"
                return HttpResponse(json.dumps(result), content_type="application/json")
        audit_auth_groups_name = "->".join(
            [
                Group.objects.get(id=auth_group_id).name
                for auth_group_id in audit_auth_groups.split(",")
            ]
        )
        result["data"]["auditors"] = audit_auth_groups
        result["data"]["auditors_display"] = audit_auth_groups_name

    return HttpResponse(json.dumps(result), content_type="application/json")


@superuser_required
def changeauditors(request):
    """设置资源组的审批流程"""
    auth_groups = request.POST.get("audit_auth_groups")
    group_name = request.POST.get("group_name")
    workflow_type = request.POST.get("workflow_type")
    result = {"status": 0, "msg": "ok", "data": []}

    # 调用工作流修改审核配置
    group_id = ResourceGroup.objects.get(group_name=group_name).group_id
    audit_auth_groups = [
        str(Group.objects.get(name=auth_group).id)
        for auth_group in auth_groups.split(",")
    ]
    try:
        Audit.change_settings(group_id, workflow_type, ",".join(audit_auth_groups))
    except Exception as msg:
        logger.error(traceback.format_exc())
        result["msg"] = str(msg)
        result["status"] = 1

    # 返回结果
    return HttpResponse(json.dumps(result), content_type="application/json")


@permission_required('sql.query_applypriv', raise_exception=True)
def get_resource_group_apply_list(request):
    user = request.user
    limit = int(request.POST.get('limit', 0))
    offset = int(request.POST.get('offset', 0))
    limit = offset + limit
    search = request.POST.get('search', '')

    query_privs = ResoueceGroupApply.objects.all()
    # 过滤搜索项，支持模糊搜索标题、用户
    if search:
        query_privs = query_privs.filter(Q(title__icontains=search) | Q(user_display__icontains=search))
    # 管理员可以看到全部数据
    if user.is_superuser:
        query_privs = query_privs
    # 拥有审核权限、可以查看组内所有工单
    elif user.has_perm('sql.query_review'):
        # 先获取用户所在资源组列表
        group_list = user_groups(user)
        group_ids = [group.group_id for group in group_list]
        query_privs = query_privs.filter(group_id__in=group_ids)
    # 其他人只能看到自己提交的工单
    else:
        query_privs = query_privs.filter(user_name=user.username)

    count = query_privs.count()
    lists = query_privs.order_by('-apply_id')[offset:limit].values(
        'apply_id', 'title', 'user_display', 'status', 'create_time', 'group_name', 'remark'
    )

    # QuerySet 序列化
    rows = [row for row in lists]

    result = {"total": count, "rows": rows}
    # 返回查询结果
    return HttpResponse(json.dumps(result, cls=ExtendJSONEncoder, bigint_as_string=True),
                        content_type='application/json')

def resource_group_apply(request):
    user = request.user
    title = request.POST['title']
    group_name = request.POST.get('group_name')
    group_id = ResourceGroup.objects.get(group_name=group_name).group_id
    remark = request.POST.get('apply_remark', '')
    result = {'status': 0, 'msg': 'ok', 'data': {}}
    apply_info = ResoueceGroupApply(
        title=title,
        status=WorkflowStatus.WAITING,
        user_name=user.username,
        user_display=user.display,
        group_id=group_id,
        group_name=group_name,
        remark=remark,
        audit_auth_groups=Audit.settings(group_id, WorkflowDict.workflow_type['resource_group']),
    )
    apply_info.save()
    logger.info(f"创建资源组申请, {apply_info}")
    # 显式指定 workflow_type
    # workflow_type = WorkflowType.RESOURCE_GROUP
    audit_handler = get_auditor(workflow=apply_info, resource_group=group_name, resource_group_id=group_id,
                                workflow_type=WorkflowType.RESOURCE_GROUP)

    # 处理审核流程
    try:
        with transaction.atomic():
            audit_handler.create_audit()
    except Exception as e:
        logger.error(f"新建审批流失败, {str(e)}")
        result["status"] = 1
        result["msg"] = "新建审批流失败, 请联系管理员"
        return HttpResponse(json.dumps(result), content_type="application/json")
    _resource_group_apply_audit_call_back(
        audit_handler.workflow.apply_id, audit_handler.audit.current_status
    )
    # 消息通知
    async_task(
        notify_for_audit,
        workflow_audit=audit_handler.audit,
        timeout=60,
        task_name=f"query-priv-apply-{audit_handler.workflow.apply_id}",
    )
    return HttpResponse(json.dumps(result), content_type="application/json")


@permission_required('sql.menu_group_purview', raise_exception=True)
def get_resource_group_apply_detail(request, apply_id):
    workflow_detail = ResoueceGroupApply.objects.get(apply_id=apply_id)
    # 获取当前审批和审批流程
    audit_handler = AuditV2(workflow=workflow_detail)
    review_info = audit_handler.get_review_info()
    # 是否可审核
    logger.info(f"获取资源组申请详情, {request.user}, {apply_id}, {4}")
    is_can_review = Audit.can_review(request.user, apply_id, 4)

    # 获取审核日志
    if workflow_detail.status == 2:
        try:
            audit_id = Audit.detail_by_workflow_id(
                workflow_id=apply_id, workflow_type=4
            ).audit_id
            last_operation_info = (
                Audit.logs(audit_id=audit_id).latest("id").operation_info
            )
        except Exception as e:
            logger.debug(f"无审核日志记录，错误信息{e}")
            last_operation_info = ""
    else:
        last_operation_info = ""

    logger.info(f"获取资源组申请详情, {workflow_detail}, {type(workflow_detail)}, {workflow_detail.status}")
    logger.info(f"获取资源组申请详情, {is_can_review}, {type(is_can_review)}")

    context = {
        "workflow_detail": workflow_detail,
        "review_info": review_info,
        "last_operation_info": last_operation_info,
        "is_can_review": is_can_review,
    }
    return render(request, "resourcegroupapplydetail.html", context)

def _resource_group_apply_audit_call_back(apply_id, workflow_status):
    """
    资源组权限申请用于工作流审核回调
    :param apply_id: 申请id
    :param workflow_status: 审核结果
    :return:
    """
    # 更新业务表状态
    apply_info = ResoueceGroupApply.objects.get(apply_id=apply_id)
    apply_info.status = workflow_status
    apply_info.save()
    # 审核通过插入权限信息，批量插入，减少性能消耗
    if workflow_status == WorkflowStatus.PASSED:
        try:
            # 获取申请记录中的用户和资源组
            user = Users.objects.get(username=apply_info.user_name)
            resource_group = ResourceGroup.objects.get(group_id=apply_info.group_id)

            # 将资源组与用户关联
            user.resource_group.add(resource_group)
            user.save()
        except Users.DoesNotExist:
            raise ValueError(f"用户 {apply_info.user_name} 不存在")
        except ResourceGroup.DoesNotExist:
            raise ValueError(f"资源组 ID {apply_info.group_id} 不存在")

@permission_required("sql.menu_group_purview", raise_exception=True)
def query_resou_group_audit(request):
    """
    查询资源组审核
    :param request:
    :return:
    """
    # 获取用户信息
    apply_id = int(request.POST["apply_id"])
    try:
        audit_status = WorkflowAction(int(request.POST["audit_status"]))
    except ValueError as e:
        return render(
            request, "error.html", {"errMsg": f"audit_status 参数错误, {str(e)}"}
        )
    audit_remark = request.POST.get("audit_remark")

    if not audit_remark:
        audit_remark = ""

    try:
        sql_query_apply = ResoueceGroupApply.objects.get(apply_id=apply_id)
    except ResoueceGroupApply.DoesNotExist:
        return render(request, "error.html", {"errMsg": "工单不存在"})
    auditor = get_auditor(workflow=sql_query_apply)
    # 使用事务保持数据一致性
    with transaction.atomic():
        try:
            workflow_audit_detail = auditor.operate(
                audit_status, request.user, audit_remark
            )
        except AuditException as e:
            return render(request, "error.html", {"errMsg": f"审核失败: {str(e)}"})
        # 统一 call back, 内部做授权和更新数据库内容
        _resource_group_apply_audit_call_back(
            auditor.audit.workflow_id, auditor.audit.current_status
        )

    # 消息通知
    async_task(
        notify_for_audit,
        workflow_audit=auditor.audit,
        workflow_audit_detail=workflow_audit_detail,
        timeout=60,
        task_name=f"resource-group-audit-{apply_id}",
    )

    return HttpResponseRedirect(reverse("sql:resourcegroupapply-detail", args=(apply_id,)))