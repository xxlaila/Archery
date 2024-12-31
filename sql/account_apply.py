# -*- coding: utf-8 -*-
"""
@File    : account_apply.py
@Time    : 2025/1/3 上午11:14
@Author  : xxlaila
@Software: PyCharm
"""

import logging
import simplejson as json
import traceback
import random
import string
from sql.utils.workflow_audit import get_auditor
from django.http import HttpResponse, HttpResponseRedirect, JsonResponse
from django.db import transaction
from django_q.tasks import async_task
from django.contrib.auth.decorators import permission_required
from django.shortcuts import render
from django.urls import reverse
from django.db.models import Q
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from common.utils.const import WorkflowStatus, WorkflowType, WorkflowAction
from common.utils.extend_json_encoder import ExtendJSONEncoder
from common.utils.const import WorkflowDict
from sql.utils.workflow_audit import Audit, AuditV2, AuditException
from sql.utils.resource_group import user_groups, user_instances
from sql.notify import notify_for_audit
from sql.models import Instance, ResourceGroup, AccountApply, InstanceAccount
from sql.engines import get_engine

logger = logging.getLogger(__name__)


@permission_required('sql.menu_queryapplylist', raise_exception=True)
def account_apply_list(request):
    """
    获取数据库账号申请列表
    :param request:
    :return:
    """
    user = request.user
    limit = int(request.POST.get('limit', 0))
    offset = int(request.POST.get('offset', 0))
    limit = offset + limit
    search = request.POST.get('search', '')

    query_privs = AccountApply.objects.all()
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
    lists = query_privs.order_by('-id')[offset:limit].values(
        'id', 'title', 'instance__instance_name', 'db_list', 'priv_type', 'table_list',
        'user_display', 'status', 'create_time', 'group_name', 'priv', 'account_name', 'host', 'password', 'note'
    )

    # QuerySet 序列化
    rows = [row for row in lists]

    result = {"total": count, "rows": rows}
    # 返回查询结果
    return HttpResponse(json.dumps(result, cls=ExtendJSONEncoder, bigint_as_string=True),
                        content_type='application/json')


@permission_required('sql.query_applypriv', raise_exception=True)
def account_apply_check(request):
    """
    创建账号前置检查
    :param request:
    :return:
    """
    instance_name = request.POST.get('instance_name')
    instance = Instance.objects.get(instance_name=instance_name)
    account_name = request.POST.get('account_name')
    password1 = request.POST.get('password1')
    password2 = request.POST.get('password2')

    # 服务端参数校验
    result = {'status': 0, 'msg': 'ok', 'data': {}}
    try:
        user_instances(request.user, db_type=['mysql']).get(instance_name=instance_name)
    except Instance.DoesNotExist:
        result['status'] = 1
        result['msg'] = '你所在组未关联该实例！'
        return HttpResponse(json.dumps(result), content_type='application/json')
    if password1:
        if password1 != password2:
            return JsonResponse({'status': 1, 'msg': '两次输入密码不一致', 'data': []})

        # TODO 目前使用系统自带验证，后续实现验证器校验
        try:
            validate_password(password1, user=None, password_validators=None)
        except ValidationError as msg:
            return JsonResponse({'status': 1, 'msg': f'{msg}', 'data': []})

    # 检查是否有同名的账号
    sql = """select user,host from mysql.user where user = '{}'""".format(account_name)
    engine = get_engine(instance=instance)
    query_result = engine.query('mysql', sql)
    check_result = query_result.to_dict()
    if len(check_result) > 0:
        exist_host = check_result[0]['host']
        result['data']['check_result'] = "'{}'@'{}'".format(account_name, exist_host)
    else:
        result['data']['check_result'] = ''

    return HttpResponse(json.dumps(result), content_type='application/json')


@permission_required('sql.query_applypriv', raise_exception=True)
def account_apply(request):
    """
    申请数据库账号
    :param request:
    :return:
    """
    # 获取用户信息
    user = request.user
    title = request.POST['title']
    instance_name = request.POST.get('instance_name')
    group_name = request.POST.get('group_name')
    group_id = ResourceGroup.objects.get(group_name=group_name).group_id
    priv_type = request.POST.get('priv_type')
    db_name = request.POST.get('db_name')
    db_list = request.POST.getlist('db_list[]')
    table_list = request.POST.getlist('table_list[]')
    priv = request.POST.get('priv')
    account_name = request.POST.get('account_name')
    host = request.POST.get('host')
    password = request.POST.get('password1')
    note = request.POST.get('remark', '')
    ins = Instance.objects.get(instance_name=instance_name)

    result = {'status': 0, 'msg': 'ok', 'data': {}}
    if not password:
        # 如果没有填密码，随机生成一个密码
        password = generate_random_str(length=16, is_digits=False)

    # 使用事务保持数据一致性
    try:
        with transaction.atomic():
            # 保存申请信息到数据库
            applyinfo = AccountApply(
                title=title,
                group_id=group_id,
                group_name=group_name,
                # 暂时使用在线查询的审批流程
                audit_auth_groups=Audit.settings(group_id, WorkflowDict.workflow_type['account']),
                user_name=user.username,
                user_display=user.display,
                instance=ins,
                priv_type=int(priv_type),
                priv=int(priv),
                account_name=account_name,
                host=host,
                password=password,
                note=note,
                status=WorkflowStatus.WAITING,
            )
            if int(priv_type) == 0:
                applyinfo.db_list = '*'
                applyinfo.table_list = ''
            if int(priv_type) == 1:
                applyinfo.db_list = ','.join(db_list)
                applyinfo.table_list = ''
            elif int(priv_type) == 2:
                applyinfo.db_list = db_name
                applyinfo.table_list = ','.join(table_list)
            applyinfo.save()
            id = applyinfo.id

            # 调用工作流插入审核信息
            audit_handler = get_auditor(workflow=applyinfo, resource_group=group_name, resource_group_id=group_id,
                                        workflow_type=WorkflowType.ACCOUNT)
            # 处理审核流程
            try:
                with transaction.atomic():
                    audit_handler.create_audit()
            except Exception as e:
                logger.error(f"新建审批流失败, {str(e)}")
                result["status"] = 1
                result["msg"] = "新建审批流失败, 请联系管理员"
                return HttpResponse(json.dumps(result), content_type="application/json")

            if audit_result['status'] == WorkflowStatus.WAITING:
                # 更新业务表审核状态,判断是否创建账号
                _account_audit_call_back(id, audit_result['data']['workflow_status'])

    except Exception as msg:
        logger.error(traceback.format_exc())
        result['status'] = 1
        result['msg'] = str(msg)
    else:
        result = audit_result
        # 消息通知
        audit_id = Audit.detail_by_workflow_id(workflow_id=id,
                                               workflow_type=WorkflowDict.workflow_type['account']).audit_id
        async_task(notify_for_audit, audit_id=audit_id, timeout=60, task_name=f'account-apply-{id}')
    return HttpResponse(json.dumps(result), content_type='application/json')


@permission_required('sql.query_review', raise_exception=True)
def account_apply_audit(request):
    """
    数据库账号申请审核
    :param request:
    :return:
    """
    # 获取用户信息
    user = request.user
    id = int(request.POST['id'])
    audit_status = int(request.POST['audit_status'])
    audit_remark = request.POST.get('audit_remark')

    if audit_remark is None:
        audit_remark = ''

    workflow_type = WorkflowDict.workflow_type['account']
    if Audit.can_review(request.user, id, workflow_type) is False:
        context = {'errMsg': '你无权操作当前工单！'}
        return render(request, 'error.html', context)

    # 使用事务保持数据一致性
    try:
        with transaction.atomic():
            audit_id = Audit.detail_by_workflow_id(workflow_id=id,
                                                   workflow_type=WorkflowDict.workflow_type['account']).audit_id

            # 调用工作流接口审核
            audit_result = Audit.audit(audit_id, audit_status, user.username, audit_remark)

            # 按照审核结果更新业务表审核状态
            audit_detail = Audit.detail(audit_id)

            if audit_detail.workflow_type == WorkflowDict.workflow_type['account']:
                # 更新业务表审核状态
                _account_audit_call_back(audit_detail.workflow_id, audit_result['data']['workflow_status'])

    except Exception as msg:
        logger.error(traceback.format_exc())
        context = {'errMsg': msg}
        return render(request, 'error.html', context)
    else:
        # 消息通知
        async_task(notify_for_audit, audit_id=audit_id, audit_remark=audit_remark, timeout=60,
                   task_name=f'account-audit-{id}')

    return HttpResponseRedirect(reverse('sql:accountapplydetail', args=(id,)))


def _account_audit_call_back(id, workflow_status):
    """
    账号申请用于工作流审核回调
    :param id: 申请id
    :param workflow_status: 审核结果
    :return:
    """
    # 更新业务表状态
    apply_info = AccountApply.objects.get(id=id)
    apply_info.status = workflow_status
    apply_info.save()
    # 审核通过创建账号
    if workflow_status == WorkflowDict.workflow_status['audit_success']:
        create_account(id)


def create_account(id):
    """
    执行创建账号
    :param id 申请id
    :return:
    """
    apply_queryset = AccountApply.objects.get(id=id)
    instance_id = apply_queryset.instance_id
    user = apply_queryset.account_name
    host = apply_queryset.host
    password = apply_queryset.password
    priv_type = apply_queryset.priv_type
    priv_code = apply_queryset.priv
    db_list = apply_queryset.db_list
    tb_list = apply_queryset.table_list
    remark = apply_queryset.note
    instance = Instance.objects.get(id=instance_id)
    grant_sql = ''

    if priv_code == 1:
        priv = 'select'
    elif priv_code == 2:
        priv = 'select, update, insert, delete'
    elif priv_code == 3:
        priv = 'select, replication slave, replication client'
    else:
        priv = 'usage'

    # 在一个事务内执行
    host_list = host.split("|")
    db_list = db_list.split(',')
    tb_list = tb_list.split(',')
    accounts = []
    for host in host_list:
        grant_sql += f"create user '{user}'@'{host}' identified by '{password}';"
        accounts.append(InstanceAccount(instance=instance, user=user, host=host, password=password, remark=remark))
        # 全局权限
        if priv_type == 0:
            grant_sql += f"GRANT {priv} ON *.* TO '{user}'@'{host}';"
        # 库权限
        elif priv_type == 1:
            for db in db_list:
                grant_sql += f"GRANT {priv} ON `{db}`.* TO '{user}'@'{host}';"
        # 表权限
        elif priv_type == 2:
            for db in db_list:
                for tb in tb_list:
                    grant_sql += f"GRANT {priv} ON `{db}`.`{tb}` TO '{user}'@'{host}';"

    engine = get_engine(instance=instance)
    exec_result = engine.execute(sql=grant_sql)
    if exec_result.error:
        return JsonResponse({'status': 1, 'msg': exec_result.error})
    # 保存到数据库
    else:
        InstanceAccount.objects.bulk_create(accounts)


def generate_random_str(length: int = 4, is_digits: bool = True) -> str:
    punctuation = r"""!#$%&'()*+,-./:;<=>?@[]^_`{|}~"""
    words = string.digits if is_digits else string.ascii_letters + string.digits
    return ''.join(random.sample(words, length))
