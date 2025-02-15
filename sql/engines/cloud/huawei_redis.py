# ！/usr/bin/env python
# -*-coding:Utf-8 -*-
# Time: 2025/1/19 16:05
# FileName: huawei_redis.py
# Author: xxlaila
# Tools: PyCharm

import os
import datetime
import pytz
import time
from typing import Optional
import logging
from typing import List, Dict
from huaweicloudsdkcore.auth.credentials import BasicCredentials
from huaweicloudsdkdcs.v2.region.dcs_region import DcsRegion
from huaweicloudsdkcore.exceptions import exceptions
# from huaweicloudsdkdcs.v2.dcs_client import DcsClient
# from huaweicloudsdkdcs.v2.model.show_instance_request import ShowInstanceRequest
# from huaweicloudsdkdcs.v2.model.create_hotkey_scan_task_request import CreateHotkeyScanTaskRequest
# from huaweicloudsdkdcs.v2.model.show_hotkey_task_details_request import ShowHotkeyTaskDetailsRequest
# from huaweicloudsdkdcs.v2.model.create_bigkey_scan_task_request import CreateBigkeyScanTaskRequest
# from huaweicloudsdkdcs.v2.model.show_bigkey_scan_task_details_request import ShowBigkeyScanTaskDetailsRequest
# from huaweicloudsdkdcs.v2.model.list_slowlog_request import ListSlowlogRequest
# from huaweicloudsdkdcs.v2.model.list_clients_request import ListClientsRequest
# from huaweicloudsdkdcs.v2.model.show_nodes_information_request import ShowNodesInformationRequest

from huaweicloudsdkdcs.v2 import *
from django.core.exceptions import ObjectDoesNotExist
from sql.models import CloudAccessKey
from sql.models import AliyunRdsConfig

logger = logging.getLogger(__name__)

def exception_handler(func):
    """统一异常处理装饰器"""
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except exceptions.ClientRequestException as err:
            logger.error(f"Huawei Cloud SDK Exception in {func.__name__}: {err}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error in {func.__name__}: {e}")
            raise
    return wrapper

class HuaweiRedis(object):
    def __init__(self, instance: Optional[str] = None, zone_list: str = "cn-north-4"):
        self.zone = zone_list
        self._client: Optional[DcsClient] = None
        self.offset = 1
        self.limit = 30
        self.product = "redis"
        self._initialize_instance_info(instance)
        self.starttime = datetime.datetime.now(pytz.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        self.endtime = (datetime.datetime.now(pytz.utc) - datetime.timedelta(minutes=120)).strftime("%Y-%m-%dT%H:%M:%SZ")

    def _initialize_instance_info(self, instance: str):
        """初始化实例信息"""
        if not instance:
            raise ValueError("Instance parameter cannot be None.")
        try:
            instance_info = AliyunRdsConfig.objects.get(instance__instance_name=instance)
            self.instance = instance_info.instance
            self.host = instance_info.instance.host
            self.port = instance_info.instance.port
            self.user = instance_info.instance.user
            self.password = instance_info.instance.password
            self.instanceid = instance_info
        except ObjectDoesNotExist:
            logger.error(f"No HuaweiRedis configuration found for instance: {instance}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error while initializing HuaweiRedis: {e}")
            raise

    def _create_client(self)-> DcsClient:
        """创建 Redis 客户端，支持缓存"""
        if not self._client:
            accesskey = CloudAccessKey.objects.filter(type="Huawei").first()
            if not accesskey:
                raise ObjectDoesNotExist("No Huawei Cloud Access Key found.")
            credentials = BasicCredentials(accesskey.raw_key_id, accesskey.raw_key_secret)
            self._client = DcsClient.new_builder() \
                .with_credentials(credentials) \
                .with_region(DcsRegion.value_of(self.zone)) \
                .build()
        return self._client

    @exception_handler
    def huawei_api_ShowInstance(self) -> dict:
        """查询实例详情"""
        try:
            client = self._client
            request = ShowInstanceRequest()
            request.instance_id = self.instanceid.instance_id
            response = client.show_instance(request)
            return response.to_dict()
        except exceptions.ClientRequestException as err:
            logger.error(f"Huawei Cloud SDK Exception: {err}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error in huawei_api_ShowInstance: {e}")
            raise

    @exception_handler
    def huawei_api_CreateHotkeyScanTask(self) -> dict:
        """创建热key分析任务"""
        try:
            client = self._client
            request = CreateHotkeyScanTaskRequest()
            request.instance_id = self.instanceid.instance_id
            response = client.create_hotkey_scan_task(request)
            return response.to_dict()
        except exceptions.ClientRequestException as err:
            logger.error(f"Huawei Cloud SDK Exception: {err}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error in huawei_api_CreateHotkeyScanTask: {e}")
            raise

    @exception_handler
    def huawei_api_ShowHotkeyTaskDetails(self) -> dict:
        """查询热key分析详情"""
        taskid = self.huawei_api_CreateHotkeyScanTask()
        try:
            client = self._client
            request = ShowHotkeyTaskDetailsRequest()
            request.instance_id = self.instanceid.instance_id
            request.hotkey_id = taskid
            response = client.show_hotkey_task_details(request)
            return response.to_dict()
        except exceptions.ClientRequestException as err:
            logger.error(f"Huawei Cloud SDK Exception: {err}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error in huawei_api_DescribeHotkeyScanTask: {e}")
            raise

    @exception_handler
    def huawei_api_CreateBigkeyScanTask(self) -> dict:
        """创建大key分析任务"""
        try:
            client = self._client
            request = CreateBigkeyScanTaskRequest()
            request.instance_id = self.instanceid.instance_id
            response = client.create_bigkey_scan_task(request)
            return response.to_dict()
        except exceptions.ClientRequestException as err:
            logger.error(f"Huawei Cloud SDK Exception: {err}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error in huawei_api_CreateBigkeyScanTask: {e}")
            raise

    @exception_handler
    def huawei_api_ShowBigkeyScanTaskDetails(self) -> dict:
        """查询大key分析详情"""
        taskid = self.huawei_api_CreateBigkeyScanTask()
        try:
            client = self._client
            request = ShowBigkeyScanTaskDetailsRequest()
            request.instance_id = self.instanceid.instance_id
            request.bigkey_id = taskid
            response = client.show_bigkey_scan_task_details(request)
            return response.to_dict()
        except exceptions.ClientRequestException as err:
            logger.error(f"Huawei Cloud SDK Exception: {err}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error in huawei_api_DescribeBigkeyScanTask: {e}")
            raise

    @exception_handler
    def huawei_api_ListSlowlog(self)  -> dict:
        """查询慢日志列表"""
        try:
            client = self._client
            request = ListSlowlogRequest()
            request.instance_id = self.instanceid.instance_id
            request.start_time = self.endtime
            request.end_time = self.starttime
            request.offset = self.offset
            request.limit = self.limit
            response = client.list_slowlog(request)
            return response.to_dict()
        except exceptions.ClientRequestException as err:
            logger.error(f"Huawei Cloud SDK Exception: {err}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error in huawei_api_ListSlowlog: {e}")
            raise

    @exception_handler
    def huawei_api_ShowNodesInformation(self)  -> List[str]:
        """查询实例节点信息"""
        try:
            client = self._client
            request = ShowNodesInformationRequest()
            request.instance_id = self.instanceid.instance_id
            response = client.show_nodes_information(request)
            result = response.to_dict()
            return [node["node_id"] for node in result.nodes]
        except exceptions.ClientRequestException as err:
            logger.error(f"Huawei Cloud SDK Exception: {err}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error in huawei_api_ShowNodesInformation: {e}")
            raise

    @exception_handler
    def huawei_api_ListClients(self) -> Dict[str, dict]:
        """查询客户端列表"""
        node_ids = self.huawei_api_ShowNodesInformation()
        all_clients_info = {}
        for node_id in node_ids:
            try:
                client = self._client
                request = ListClientsRequest()
                request.instance_id = self.instanceid.instance_id
                request.node_id = node_id
                request.offset = self.offset
                request.limit = self.limit
                response = client.list_clients(request)
                all_clients_info[node_id] = response.to_dict()
            except exceptions.ClientRequestException as err:
                logger.error(f"Huawei Cloud SDK Exception for node {node_id}: {err}")
                # 根据您的需求决定是否继续处理其他节点或中断
                continue
            except Exception as e:
                logger.error(f"Unexpected error in huawei_api_ListClients for node {node_id}: {e}")
                # 同上，决定是否继续处理其他节点
                continue