# -*- coding: utf-8 -*-
"""
@File    : tencent_redis.py
@Time    : 2024/12/30 11:51 上午
@Author  : xxlaila
@Software: PyCharm
"""

import json
import logging
from django.core.exceptions import ObjectDoesNotExist
from tencentcloud.common import credential
from tencentcloud.common.profile.client_profile import ClientProfile
from tencentcloud.common.profile.http_profile import HttpProfile
from tencentcloud.common.exception.tencent_cloud_sdk_exception import TencentCloudSDKException
from tencentcloud.redis.v20180412 import redis_client, models
from sql.models import CloudAccessKey
from sql.models import AliyunRdsConfig

logger = logging.getLogger(__name__)

class TencentRedis:
    def __init__(self, instance=None, zone_list: str = "ap-beijing"):
        self.product = "redis"
        self.zone = zone_list
        try:
            if not instance:
                raise ValueError("Instance parameter cannot be None.")
            instancename = AliyunRdsConfig.objects.get(instance__instance_name=instance)
            self.instanceid = instancename
            accesskey = CloudAccessKey.objects.filter(type="Tencent").first()
            if not accesskey:
                raise ObjectDoesNotExist("No Tencent Cloud Access Key found.")
            self.cred = credential.Credential(accesskey.raw_key_id, accesskey.raw_key_secret)
        except ObjectDoesNotExist as e:
            logger.error(f"No TencentRDS configuration found for instance: {instance} - {e}")
            raise
        except ValueError as ve:
            logger.error(str(ve))
            raise
        except Exception as e:
            logger.error(f"Unexpected error while initializing TencentRedis: {e}")
            raise

    def _create_redis_client(self):
        """Create and return a RedisClient instance."""
        try:
            httpProfile = HttpProfile()
            httpProfile.endpoint = "redis.tencentcloudapi.com"
            clientProfile = ClientProfile()
            clientProfile.httpProfile = httpProfile
            return redis_client.RedisClient(self.cred, self.zone, clientProfile)
        except Exception as e:
            logger.error(f"Error creating RedisClient: {e}")
            raise

    def tencent_api_DescribeInstances(self):
        """腾讯云redis 实例列表接口"""
        try:
            client = self._create_redis_client()
            req = models.DescribeInstancesRequest()
            params = {
                "Limit": 20,
                'InstanceIds': [self.instanceid.rds_dbinstanceid]
            }
            req.from_json_string(json.dumps(params))
            resp = client.DescribeInstances(req)
            return json.loads(resp.to_json_string())
        except TencentCloudSDKException as err:
            logger.error(f"Tencent Cloud SDK Exception: {err}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            raise

    def tencent_api_DescribeInstanceMonitorBigKey(self, reqtime):
        """腾讯云redis 实例大key接口"""
        try:
            client = self._create_redis_client()
            req = models.DescribeInstanceMonitorBigKeyRequest()
            params = {
                'InstanceId': self.instanceid.rds_dbinstanceid,
                'ReqType': 2,
                'Date': reqtime
            }
            req.from_json_string(json.dumps(params))
            resp = client.DescribeInstanceMonitorBigKey(req)
            return json.loads(resp.to_json_string())
        except TencentCloudSDKException as err:
            logger.error(f"Tencent Cloud SDK Exception: {err}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            raise

    def tencent_api_DescribeInstanceMonitorHotKey(self):
        """腾讯云redis 实例热key接口"""
        try:
            client = self._create_redis_client()
            req = models.DescribeInstanceMonitorHotKeyRequest()
            params = {
                'InstanceId': self.instanceid.rds_dbinstanceid,
                'SpanType': 4
            }
            req.from_json_string(json.dumps(params))
            resp = client.DescribeInstanceMonitorHotKey(req)
            return json.loads(resp.to_json_string())
        except TencentCloudSDKException as err:
            logger.error(f"Tencent Cloud SDK Exception: {err}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            raise
