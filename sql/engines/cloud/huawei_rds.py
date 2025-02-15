# ！/usr/bin/env python
# -*-coding:Utf-8 -*-
# Time:  2025/1/19 15:03
# FileName: huawei_rds.py
# Author: xxlaila
# Tools: PyCharm

import os
import datetime
import pytz
import logging
from huaweicloudsdkcore.auth.credentials import BasicCredentials
from huaweicloudsdkrds.v3.region.rds_region import RdsRegion
from huaweicloudsdkcore.exceptions import exceptions
from huaweicloudsdkrds.v3 import *
# from huaweicloudsdkrds.v3.rds_client import RdsClient
# from huaweicloudsdkrds.v3.model.list_instances_request import ListInstancesRequest
# from huaweicloudsdkrds.v3.model.list_slow_logs_new_request import ListSlowLogsNewRequest
# from huaweicloudsdkrds.v3.model.list_slowlog_statistics_request import ListSlowlogStatisticsRequest
from django.core.exceptions import ObjectDoesNotExist
from sql.engines.mysql import MysqlEngine
from sql.models import CloudAccessKey
from sql.models import AliyunRdsConfig


logger = logging.getLogger(__name__)

class HuaweiRDS(MysqlEngine):
    def __init__(self, instance=None, zone_list: str = "cn-north-4"):
        super().__init__()
        self.zone = zone_list
        self.offset = 1
        self.limit = 30
        self.product = "mysql"
        self._initialize_instance_info(instance)
        self.starttime = datetime.datetime.now(pytz.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        self.endtime = (datetime.datetime.now(pytz.utc) - datetime.timedelta(minutes=120)).strftime("%Y-%m-%dT%H:%M:%SZ")

    def _initialize_instance_info(self, instance):
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
            logger.error(f"No HuaweiRDS configuration found for instance: {instance}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error while initializing HuaweiRDS: {e}")
            raise

    def _create_client(self):
        """创建RDS客户端"""
        try:
            accesskey = CloudAccessKey.objects.filter(type="Huawei").first()
            if not accesskey:
                raise ObjectDoesNotExist("No Huawei Cloud Access Key found.")
            credentials = BasicCredentials(accesskey.raw_key_id, accesskey.raw_key_secret)
            client = RdsClient.new_builder() \
                .with_credentials(credentials) \
                .with_region(RdsRegion.value_of(self.zone)) \
                .build()
            return client
        except Exception as e:
            logger.error(f"Error creating DbbrainClient: {e}")
            raise

    def huawei_api_DescribeDBInstances(self):
        """
        查询实例列表详情
        """
        try:
            client = self._create_client()  # 获取客户端实例
            request = ListInstancesRequest()
            request.id = self.instanceid.instance_id
            request.datastore_type = "MySQL"
            response = client.list_instances(request)  # 调用查询实例列表详情接口
            return response.to_dict()  # 将返回结果转换为字典格式
        except exceptions.ClientRequestException as err:
            logger.error(f"Huawei Cloud SDK Exception: {err}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error in huawei_api_DescribeDBInstances: {e}")
            raise

    def huawei_api_ListSlowLogsNew(self):
        """
        查询慢日志列表
        """
        try:
            client = self._create_client()  # 创建RDS客户端
            request = ListSlowLogsNewRequest()
            request.instance_id = self.instanceid.instance_id
            request.start_time = self.endtime
            request.end_time = self.starttime
            request.offset = self.offset
            request.limit = self.limit
            response = client.list_slow_logs(request)  # 调用查询慢日志列表接口
            return response.to_dict()  # 将返回结果转换为字典格式
        except exceptions.ClientRequestException as err:
            logger.error(f"Huawei Cloud SDK Exception: {err}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error in huawei_api_ListSlowLogsNew: {e}")
            raise

    def huawei_api_ListSlowlogStatistics(self):
        """
        获取慢日志统计信息
        """
        try:
            client = self._create_client()  # 创建RDS客户端
            request = ListSlowlogStatisticsRequest()
            request.instance_id = self.instanceid.instance_id
            request.start_time = self.endtime
            request.end_time = self.starttime
            request.cur_page = self.offset
            request.per_page = self.limit
            request.type = "ALL"
            response = client.list_slowlog_statistics(request)  # 调用获取慢日志统计信息接口
            return response.to_dict()  # 将返回结果转换为字典格式
        except exceptions.ClientRequestException as err:
            logger.error(f"Huawei Cloud SDK Exception: {err}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error in huawei_api_ListSlowlogStatistics: {e}")
            raise