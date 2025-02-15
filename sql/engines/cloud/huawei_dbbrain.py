# ！/usr/bin/env python
# -*-coding:Utf-8 -*-
# Time: 2025/1/19 19:37
# FileName: huawei_dbbrain.py
# Author: xxlaila
# Tools: PyCharm

import os
import logging
import pytz
import datetime
from huaweicloudsdkcore.auth.credentials import BasicCredentials
from huaweicloudsdkdas.v3.region.das_region import DasRegion
from huaweicloudsdkcore.exceptions import exceptions
# from huaweicloudsdkdas.v3.das_client import DasClient
# from huaweicloudsdkdas.v3.model.list_space_analysis_request import ListSpaceAnalysisRequest
from huaweicloudsdkdas.v3 import *
from sql.engines.mysql import MysqlEngine
from django.core.exceptions import ObjectDoesNotExist
from sql.models import CloudAccessKey
from sql.models import AliyunRdsConfig
from sql.engines.cloud.huawei_redis import exception_handler

logger = logging.getLogger(__name__)

class HuaweiDBBrain(MysqlEngine):
    def __init__(self, instance=None, zone_list: str = "cn-north-4"):
        super().__init__()
        self.zone = zone_list
        self.offset = 1
        self.limit = 30
        self.product = "mysql"
        self._initialize_instance_info(instance)
        self.starttime = datetime.datetime.now(pytz.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        self.endtime = (datetime.datetime.now(pytz.utc) - datetime.timedelta(minutes=120)).strftime("%Y-%m-%dT%H:%M:%SZ")
        self._cli = None

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
            logger.error(f"No HuaweiDBBrain configuration found for instance: {instance}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error while initializing HuaweiDBBrain: {e}")
            raise

    def _create_client(self):
        """创建DBbrain客户端"""
        try:
            accesskey = CloudAccessKey.objects.filter(type="Huawei").first()
            if not accesskey:
                raise ObjectDoesNotExist("No Huawei Cloud Access Key found.")
            credentials = BasicCredentials(accesskey.raw_key_id, accesskey.raw_key_secret)
            client = DasClient.new_builder() \
                .with_credentials(credentials) \
                .with_region(DasRegion.value_of(self.zone)) \
                .build()
            return client
        except Exception as e:
            logger.error(f"Error creating DbbrainClient: {e}")
            raise

    @exception_handler
    def huawei_api_ListSpaceAnalysis(self):
        """查询空间分析列表"""
        try:
            client = self._create_client()
            request = ListSpaceAnalysisRequest()
            request.instance_id = self.instanceid.instance_id
            request.object_type = "database"
            request.datastore_type = "MySQL"
            response = client.list_space_analysis(request)
            return response.to_dict()
        except exceptions.ClientRequestException as err:
            logger.error(f"Huawei Cloud SDK Exception: {err}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error in huawei_api_ListSpaceAnalysis: {e}")
            raise

