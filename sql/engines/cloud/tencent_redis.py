# -*- coding: utf-8 -*-
"""
@File    : tencent_redis.py
@Time    : 2024/12/30 11:51 上午
@Author  : xxlaila
@Software: PyCharm
"""
import types
import json
import logging
import datetime
from django.core.exceptions import ObjectDoesNotExist
from tencentcloud.common import credential
from tencentcloud.common.profile.client_profile import ClientProfile
from tencentcloud.common.profile.http_profile import HttpProfile
from tencentcloud.common.exception.tencent_cloud_sdk_exception import TencentCloudSDKException
from tencentcloud.redis.v20180412 import redis_client, models
from sql.models import CloudAccessKey
from sql.models import AliyunRdsConfig

logger = logging.getLogger(__name__)

current_time = datetime.datetime.now()
starttime = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
endtime = (current_time - datetime.timedelta(hours=12)).strftime("%Y-%m-%d %H:%M:%S")

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

    def tencent_api_DescribeInstanceMonitorSIP(self):
        """
        查询实例访问来源信息
        :return:
        """
        try:
            client = self._create_redis_client()
            req = models.DescribeInstanceMonitorSIPRequest()
            params = {
                'InstanceId': self.instanceid.rds_dbinstanceid,
            }
            req.from_json_string(json.dumps(params))
            resp = client.DescribeInstanceMonitorSIP(req)
            return json.loads(resp.to_json_string())
        except TencentCloudSDKException as err:
            logger.error(f"Tencent Cloud SDK Exception: {err}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            raise

    def tencent_api_DescribeInstanceMonitorTookDist(self, reqtime):
        """
        查询实例访问的耗时分布
        :return:
        """
        try:
            client = self._create_redis_client()
            req = models.DescribeInstanceMonitorTookDistRequest()
            params = {
                'InstanceId': self.instanceid.rds_dbinstanceid,
                "Date": reqtime,
                "SpanType": 4
            }
            req.from_json_string(json.dumps(params))
            resp = client.DescribeInstanceMonitorTookDist(req)
            return json.loads(resp.to_json_string())
        except TencentCloudSDKException as err:
            logger.error(f"Tencent Cloud SDK Exception: {err}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            raise

    def tencent_api_DescribeInstanceMonitorTopNCmd(self):
        """
        查询实例访问命令
        :return:
        """
        try:
            client = self._create_redis_client()
            req = models.DescribeInstanceMonitorTopNCmdRequest()
            params = {
                'InstanceId': self.instanceid.rds_dbinstanceid,
                "SpanType": 4
            }
            req.from_json_string(json.dumps(params))
            resp = client.DescribeInstanceMonitorTopNCmd(req)
            return json.loads(resp.to_json_string())
        except TencentCloudSDKException as err:
            logger.error(f"Tencent Cloud SDK Exception: {err}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            raise

    def tencent_api_DescribeInstanceMonitorTopNCmdTook(self):
        """
        查询实例CPU耗时
        :return:
        """
        try:
            client = self._create_redis_client()
            req = models.DescribeInstanceMonitorTopNCmdTookRequest()
            params = {
                'InstanceId': self.instanceid.rds_dbinstanceid,
                "SpanType": 4
            }
            req.from_json_string(json.dumps(params))
            resp = client.DescribeInstanceMonitorTopNCmdTook(req)
            return json.loads(resp.to_json_string())
        except TencentCloudSDKException as err:
            logger.error(f"Tencent Cloud SDK Exception: {err}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            raise

    def tencent_api_DescribeSlowLog(self):
        """
        查询redis慢日志
        请求参数:{
            "InstanceId": "crs-asda****",
            "EndTime": "2019-09-09 12:12:41",
            "BeginTime": "2019-09-08 12:12:41"
        }
        :return:
        """
        try:
            client = self._create_redis_client()
            req = models.DescribeSlowLogRequest()
            params = {
                'InstanceId': self.instanceid.rds_dbinstanceid,
                "BeginTime": endtime,
                "EndTime": starttime,
                "Limit": 50,
                "Role": "master"
            }
            req.from_json_string(json.dumps(params))
            resp = client.DescribeSlowLog(req)
            return json.loads(resp.to_json_string())
        except TencentCloudSDKException as err:
            logger.error(f"Tencent Cloud SDK Exception: {err}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            raise
