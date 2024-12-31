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
        """
        查询实例列表详情
        :param instancetypes:
        :param instancename:
        :return:
        """
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

    def tencent_api_CreateDatabase(self):
        """
        创建数据库
        :return:
        """
        try:
            client = self._create_dbbrain_client()
            req = models.CreateDatabaseRequest()
            params = {
                "InstanceId": self.instanceid.instance_id,
                "DBName": "sdasd",
                "CharacterSetName": "utf8mb4"
            }
            req.from_json_string(json.dumps(params))
            resp = client.CreateDatabase(req)
            return json.loads(resp.to_json_string())
        except TencentCloudSDKException as err:
            logger.error(f"Tencent Cloud SDK Exception: {err}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            raise
        except TencentCloudSDKException as err:
            logger.error(f"Tencent Cloud SDK Exception: {err}")
            raise

    def tencent_api_DeleteDatabase(self, dbname):
        """
        删除数据库
        :param dbname:
        :return:
        """
        try:
            client = self._create_dbbrain_client()
            req = models.DeleteDatabaseRequest()
            params = {
                "InstanceId": self.instanceid.instance_id,
                "DBName": "sdasd"
            }
            req.from_json_string(json.dumps(params))
            resp = client.DeleteDatabase(req)
            return json.loads(resp.to_json_string())
        except TencentCloudSDKException as err:
            logger.error(f"Tencent Cloud SDK Exception: {err}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            raise
        except TencentCloudSDKException as err:
            logger.error(f"Tencent Cloud SDK Exception: {err}")
            raise

    def tencent_api_DescribeDatabases(self, dbname):
        """
        查询数据库列表
        :param dbname:
        :return:
        """
        try:
            client = self._create_dbbrain_client()
            req = models.DescribeDatabasesRequest()
            params = {
                "InstanceId": self.instanceid.instance_id,
                "Offset": 0,
                "Limit": 100
            }
            req.from_json_string(json.dumps(params))
            resp = client.DescribeDatabases(req)
            return json.loads(resp.to_json_string())
        except TencentCloudSDKException as err:
            logger.error(f"Tencent Cloud SDK Exception: {err}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            raise
        except TencentCloudSDKException as err:
            logger.error(f"Tencent Cloud SDK Exception: {err}")
            raise

    def tencent_api_DescribeTables(self, dbname):
        """
        查询数据库表
        :param dbname:
        :return:
        """
        try:
            client = self._create_dbbrain_client()
            req = models.DescribeTablesRequest()
            params = {
                "InstanceId": self.instanceid.instance_id,
                "Database": "dsasdas",
                "Offset": 0,
                "Limit": 2000
            }
            req.from_json_string(json.dumps(params))
            resp = client.DescribeTables(req)
            return json.loads(resp.to_json_string())
        except TencentCloudSDKException as err:
            logger.error(f"Tencent Cloud SDK Exception: {err}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            raise
        except TencentCloudSDKException as err:
            logger.error(f"Tencent Cloud SDK Exception: {err}")
            raise

    def tencent_api_CreateAccounts(self, dbname):
        """
        创建数据库账号
        :param dbname:
        :return:
        """
        try:
            client = self._create_dbbrain_client()
            req = models.CreateAccountsRequest()
            params = {
                "InstanceId": self.instanceid.instance_id,
                "Accounts": [
                    {
                        "AccountName": "test",
                        "Host": "%",
                    }
                ],
                "Password": "2312321",
                "Description": "测试",
                "MaxUserConnections": 10240
            }
            req.from_json_string(json.dumps(params))
            resp = client.CreateAccounts(req)
            return json.loads(resp.to_json_string())
        except TencentCloudSDKException as err:
            logger.error(f"Tencent Cloud SDK Exception: {err}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            raise

    def tencent_api_DeleteAccounts(self):
        """
        删除数据库账号
        :return:
        """
        try:
            client = self._create_dbbrain_client()
            req = models.DeleteAccountsRequest()
            params = {
                "InstanceId": self.instanceid.instance_id,
                "Accounts": [
                    {
                        "User": "sdsad",
                        "Host": "%"
                    }
                ]
            }
            req.from_json_string(json.dumps(params))
            resp = client.DeleteAccounts(req)
            return json.loads(resp.to_json_string())
        except TencentCloudSDKException as err:
            logger.error(f"Tencent Cloud SDK Exception: {err}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            raise

    def tencent_api_ModifyAccountDescription(self):
        """
        修改数据库账号描述
        :return:
        """
        try:
            client = self._create_dbbrain_client()
            req = models.ModifyAccountDescriptionRequest()
            params = {
                "InstanceId": self.instanceid.instance_id,
                "Accounts": [
                    {
                        "User": "dsadas",
                        "Host": "sdas"
                    }
                ],
                "Description": "sdsad"
            }
            req.from_json_string(json.dumps(params))
            resp = client.ModifyAccountDescription(req)
            return json.loads(resp.to_json_string())
        except TencentCloudSDKException as err:
            logger.error(f"Tencent Cloud SDK Exception: {err}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            raise

    def tencent_api_ModifyAccountHost(self):
        """
        修改数据库账号主机
        :return:
        """
        try:
            client = self._create_dbbrain_client()
            req = models.ModifyAccountHostRequest()
            params = {
                "InstanceId": self.instanceid.instance_id,
                "User": "sdadsa",
                "Host": "sdasd",
                "NewHost": "sdasd"
            }
            req.from_json_string(json.dumps(params))
            resp = client.ModifyAccountHost(req)
            return json.loads(resp.to_json_string())
        except TencentCloudSDKException as err:
            logger.error(f"Tencent Cloud SDK Exception: {err}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            raise

    def tencent_api_ModifyAccountPassword(self):
        """
        修改数据库账号密码
        :return:
        """
        try:
            client = self._create_dbbrain_client()
            req = models.ModifyAccountPasswordRequest()
            params = {
                "InstanceId": self.instanceid.instance_id,
                "NewPassword": "sdasd",
                "Accounts": [
                    {
                        "User": "sdasd",
                        "Host": "sdasd"
                    }
                ]
            }
            req.from_json_string(json.dumps(params))
            resp = client.ModifyAccountPassword(req)
            return json.loads(resp.to_json_string())
        except TencentCloudSDKException as err:
            logger.error(f"Tencent Cloud SDK Exception: {err}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error: {e}")

    def tencent_api_ModifyAccountPrivileges(self):
        """
        修改数据库账号权限
        :return:
        """
        try:
            client = self._create_dbbrain_client()
            req = models.ModifyAccountPrivilegesRequest()
            params = {
                "InstanceId": self.instanceid.instance_id,
                "Accounts": [
                    {
                        "User": "dasd",
                        "Host": "sdasd"
                    }
                ],
                "GlobalPrivileges": [
                    "\"SELECT\",\"INSERT\",\"UPDATE\",\"DELETE\",\"CREATE\", \"PROCESS\", \"DROP\",\"REFERENCES\",\"INDEX\",\"ALTER\",\"SHOW DATABASES\",\"CREATE TEMPORARY TABLES\",\"LOCK TABLES\",\"EXECUTE\",\"CREATE VIEW\",\"SHOW VIEW\",\"CREATE ROUTINE\",\"ALTER ROUTINE\",\"EVENT\",\"TRIGGER\",\"CREATE USER\",\"RELOAD\",\"REPLICATION CLIENT\",\"REPLICATION SLAVE\"。"],
                "DatabasePrivileges": [
                    {
                        "Privileges": [
                            "\"SELECT\",\"INSERT\",\"UPDATE\",\"DELETE\",\"CREATE\", \"PROCESS\", \"DROP\",\"REFERENCES\",\"INDEX\",\"ALTER\",\"SHOW DATABASES\",\"CREATE TEMPORARY TABLES\",\"LOCK TABLES\",\"EXECUTE\",\"CREATE VIEW\",\"SHOW VIEW\",\"CREATE ROUTINE\",\"ALTER ROUTINE\",\"EVENT\",\"TRIGGER\",\"CREATE USER\",\"RELOAD\",\"REPLICATION CLIENT\",\"REPLICATION SLAVE\"。"],
                        "Database": "dsadsa"
                    }
                ],
                "TablePrivileges": [
                    {
                        "Database": "dsadsa",
                        "Table": "sdasd",
                        "Privileges": [
                            "\"SELECT\",\"INSERT\",\"UPDATE\",\"DELETE\",\"CREATE\", \"PROCESS\", \"DROP\",\"REFERENCES\",\"INDEX\",\"ALTER\",\"SHOW DATABASES\",\"CREATE TEMPORARY TABLES\",\"LOCK TABLES\",\"EXECUTE\",\"CREATE VIEW\",\"SHOW VIEW\",\"CREATE ROUTINE\",\"ALTER ROUTINE\",\"EVENT\",\"TRIGGER\",\"CREATE USER\",\"RELOAD\",\"REPLICATION CLIENT\",\"REPLICATION SLAVE\"。"]
                    }
                ],
                "ModifyAction": "grant"
            }
            req.from_json_string(json.dumps(params))
            resp = client.ModifyAccountPrivileges(req)
            return json.loads(resp.to_json_string())
        except TencentCloudSDKException as err:
            logger.error(f"Tencent Cloud SDK Exception: {err}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            raise

    def tencent_api_DescribeSlowLogData(self):
        """
        查询实例慢日志, mysql 接口
        :return:
        """
        try:
            client = self._create_dbbrain_client()
            req = models.DescribeSlowLogDataRequest()
            params = {
                "InstanceId": self.instanceid.instance_id,
                "StartTime": 1585142640,
                "EndTime": 1585142640,
                "Offset": 0,
                "Limit": 100
            }
            req.from_json_string(json.dumps(params))
            resp = client.DescribeSlowLogData(req)
            return json.loads(resp.to_json_string())
        except TencentCloudSDKException as err:
            logger.error(f"Tencent Cloud SDK Exception: {err}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            raise