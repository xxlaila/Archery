# -*- coding: utf-8 -*-
"""
@File    : tencent_rds.py
@Time    : 2024/12/23 7:47 下午
@Author  : xxlaila
@Software: PyCharm
"""
import json, os
from tencentcloud.common.profile.client_profile import ClientProfile
from tencentcloud.common.profile.http_profile import HttpProfile
from tencentcloud.common.exception.tencent_cloud_sdk_exception import TencentCloudSDKException
from tencentcloud.dbbrain.v20210527 import dbbrain_client, models
import datetime
from showsql.utils.cloud_comm import Tencent_Secret, Tencent_zone
from sql.engines.mysql import MysqlEngine
import logging

starttime = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
endtime = (datetime.datetime.now()+datetime.timedelta(minutes=-60)).strftime("%Y-%m-%d %H:%M:%S")

logger = logging.getLogger(__name__)

class TencentDBSlowSql(MysqlEngine):

    def __init__(self, zone_list: str = "ap-beijing", instanceid: str = ''):
        super().__init__(instanceid=instanceid)
        self.db_type = "mysql"
        self.instanceid = instanceid
        self.zone = zone_list
        self.hours = (datetime.datetime.now() - datetime.timedelta(hours=8)).strftime("%Y-%m-%d %H:%M:%S")
        self.offset = 1
        self.limit = 30
        self.product = "mysql"
        self.md5 = "1443425648658409903"

    def _create_client(self):
        """
        创建并返回一个 DbbrainClient 实例
        """
        httpProfile = HttpProfile()
        httpProfile.endpoint = "dbbrain.tencentcloudapi.com"
        clientProfile = ClientProfile()
        clientProfile.httpProfile = httpProfile
        return dbbrain_client.DbbrainClient(Tencent_Secret(), self.zone, clientProfile)

    def _make_request(self, client, request_class, params):
        """
        创建并发送请求，返回响应
        """
        try:
            req = request_class()
            req.from_json_string(json.dumps(params))
            resp = client.send(req)
            return json.loads(resp.to_json_string())
        except TencentCloudSDKException as err:
            logger.error(f"Tencent Cloud SDK Exception: {err}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            raise

    def get_describe_slow_log_top_sqls(self):
        """
        获取慢日志top sql
        """
        client = self._create_client()
        params = {
            "InstanceId": self.instanceid,
            "StartTime": endtime,
            "EndTime": starttime,
            "Product": self.product
        }
        return self._make_request(client, models.DescribeSlowLogTopSqlsRequest, params)

    def get_describe_user_sql_advice(self, schema, sqltext):
        """
        获取SQL优化建议
        """
        client = self._create_client()
        params = {
            "InstanceId": self.instanceid,
            "Schema": schema,
            "SqlText": sqltext,
            "Product": self.product
        }
        return self._make_request(client, models.DescribeUserSqlAdviceRequest, params)

    def process_slow_log_results(self):
        results = self.get_describe_slow_log_top_sqls()
        for row in results.get('Rows', []):
            schema = row.get('Schema')
            sqltext = row.get('SqlText') or row.get('SqlTemplate')
            if not schema or not sqltext:
                continue
            logger.info(f"Schema: {schema}, SqlText: {sqltext}")
            try:
                advice = self.get_describe_user_sql_advice(schema, sqltext)
                logger.info(f"Advice for SQL: {advice}")
            except Exception as e:
                logger.error(f"Failed to get advice for SQL: {e}")

    def get_describe_slow_logs(self):
        """
        获取慢日志明细
        """
        client = self._create_client()
        params = {
            "Product": self.product,
            "InstanceId": self.instanceid,
            "Md5": self.md5,
            "StartTime": endtime,
            "EndTime": starttime,
            "Offset": 0,
            "Limit": 100
        }
        return self._make_request(client, models.DescribeSlowLogsRequest, params)

    def process_describe_slow_logs(self):
        """
        处理慢日志明细并生成字典列表用于写入数据库
        :return: 包含慢日志信息的字典列表
        """
        slow_logs_response = self.get_describe_slow_logs()
        slow_logs = slow_logs_response.get("Response", {}).get("Rows", [])
        processed_logs = []
        for log in slow_logs:
            sql_text = log.get("SqlText", "").replace("\n", " ")
            processed_log = {
                "Database": log.get("Database"),
                "LockTime": log.get("LockTime"),
                "QueryTime": log.get("QueryTime"),
                "RowsExamined": log.get("RowsExamined"),
                "RowsSent": log.get("RowsSent"),
                "SqlText": sql_text,
                "Timestamp": log.get("Timestamp"),
                "UserHost": log.get("UserHost"),
                "UserName": log.get("UserName")
            }
            processed_logs.append(processed_log)
        return processed_logs