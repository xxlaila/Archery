# -*- coding: utf-8 -*-
"""
@File    : tencent_rds.py
@Time    : 2024/12/30 7:09 下午
@Author  : xxlaila
@Software: PyCharm
"""
import json
import json
import types
import logging
from tencentcloud.common import credential
from django.core.exceptions import ObjectDoesNotExist
from tencentcloud.common.profile.client_profile import ClientProfile
from tencentcloud.common.profile.http_profile import HttpProfile
from tencentcloud.common.exception.tencent_cloud_sdk_exception import TencentCloudSDKException
from tencentcloud.cdb.v20170320 import cdb_client, models
from sql.engines.mysql import MysqlEngine
from sql.models import CloudAccessKey
from sql.models import AliyunRdsConfig

logger = logging.getLogger(__name__)

class TencentRDS(MysqlEngine):

    def __init__(self, instance=None, zone_list: str = "ap-beijing"):
        super().__init__()
        self.zone = zone_list
        self.offset = 1
        self.limit = 30
        self.product = "mysql"
        try:
            if not instance:
                raise ValueError("Instance parameter cannot be None.")
            instance_info = AliyunRdsConfig.objects.get(instance__instance_name=instance)
            self.instance = instance_info.instance
            self.host = instance_info.instance.host
            self.port = instance_info.instance.port
            self.user = instance_info.instance.user
            self.password = instance_info.instance.password
            self.instanceid = instance_info
        except ObjectDoesNotExist:
            logger.error(f"No TencentRDS configuration found for instance: {instance}")
            raise
        except ValueError as ve:
            logger.error(str(ve))
            raise
        except Exception as e:
            logger.error(f"Unexpected error while initializing TencentRDS: {e}")
            raise

    def _create_dbbrain_client(self):
        """Create and return a DbbrainClient instance."""
        try:
            httpProfile = HttpProfile()
            httpProfile.endpoint = "cdb.tencentcloudapi.com"
            clientProfile = ClientProfile()
            clientProfile.httpProfile = httpProfile
            accesskey = CloudAccessKey.objects.filter(type="Tencent").first()
            if not accesskey:
                raise ObjectDoesNotExist("No Tencent Cloud Access Key found.")
            cred = credential.Credential(accesskey.raw_key_id, accesskey.raw_key_secret)

            return cdb_client.CdbClient(cred, self.zone, clientProfile)
        except Exception as e:
            logger.error(f"Error creating DbbrainClient: {e}")
            raise

    def tencent_api_DescribeDBInstances(self, instancetypes, instancename):
        try:
            client = self._create_dbbrain_client()
            req = models.DescribeDBInstancesRequest()
            params = {
                "InstanceTypes": [int(instancetypes)],
                "InstanceIds": [instancename]
            }
            req.from_json_string(json.dumps(params))
            resp = client.DescribeDBInstances(req)
            return json.loads(resp.to_json_string())
        except TencentCloudSDKException as err:
            logger.error(f"Tencent Cloud SDK Exception: {err}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            raise
