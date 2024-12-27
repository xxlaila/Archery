# -*- coding: utf-8 -*-
"""
@File    : tencent_rds.py
@Time    : 2024/12/23 7:47 下午
@Author  : xxlaila
@Software: PyCharm
"""
import json, os
from tencentcloud.common import credential
from django.core.exceptions import ObjectDoesNotExist
from tencentcloud.common.profile.client_profile import ClientProfile
from tencentcloud.common.profile.http_profile import HttpProfile
from tencentcloud.common.exception.tencent_cloud_sdk_exception import TencentCloudSDKException
from tencentcloud.dbbrain.v20210527 import dbbrain_client, models
import datetime
from sql.engines.mysql import MysqlEngine
from sql.models import CloudAccessKey
from sql.models import AliyunRdsConfig
import logging

starttime = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
endtime = (datetime.datetime.now()+datetime.timedelta(minutes=-60)).strftime("%Y-%m-%d %H:%M:%S")

logger = logging.getLogger(__name__)

class TencentRDS(MysqlEngine):

    def __init__(self, instance=None, zone_list: str = "ap-beijing"):
        super().__init__()
        self.zone = zone_list
        self.offset = 1
        self.limit = 30
        self.product = "mysql"
        self.md5 = "1443425648658409903"
        self.current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
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
            httpProfile.endpoint = "dbbrain.tencentcloudapi.com"
            clientProfile = ClientProfile()
            clientProfile.httpProfile = httpProfile
            accesskey = CloudAccessKey.objects.filter(type="Tencent").first()
            if not accesskey:
                raise ObjectDoesNotExist("No Tencent Cloud Access Key found.")
            cred = credential.Credential(accesskey.raw_key_id, accesskey.raw_key_secret)

            return dbbrain_client.DbbrainClient(cred, self.zone, clientProfile)
        except Exception as e:
            logger.error(f"Error creating DbbrainClient: {e}")
            raise

    def get_describe_slow_log_top_sqls(self):
        """
        获取慢日志top sql
        """
        try:
            client = self._create_dbbrain_client()
            req = models.DescribeSlowLogTopSqlsRequest()
            params = {
                "InstanceId": self.instanceid.rds_dbinstanceid,
                "StartTime": endtime,
                "EndTime": starttime,
                "Product": self.product
            }
            req.from_json_string(json.dumps(params))
            resp = client.DescribeSlowLogTopSqls(req)
            return json.loads(resp.to_json_string())
        except TencentCloudSDKException as err:
            logger.error(f"Tencent Cloud SDK Exception: {err}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            raise

    def process_slow_log_top_sqls_results(self):
        """
        处理慢查询日志中的top SQL结果。
        本函数通过调用get_describe_slow_log_top_sqls方法获取慢查询日志数据，
        并对查询结果进行解析和重新组织，提取出所需的SQL性能指标信息。
        Returns:
            list: 包含解析后的慢查询SQL信息的列表。
        """
        extracted_data = []
        response = self.get_describe_slow_log_top_sqls()
        for row in response.get('Rows', []):
            extracted_row ={
                'LockTimeMax': row['LockTimeMax'],
                'ParseTotalRowCounts': row['RowsExamined'],
                'MySQLTotalExecutionTimes': row['QueryTime'],
                'QueryTimeMax': row['QueryTimeMax'],
                'ReturnTotalRowCounts': row['RowsSent'],
                'MySQLTotalExecutionCounts': row['ExecTimes'],
                'SqlTemplate': row['SqlTemplate'].replace('\n', ' '),
                'SQLText': row['SqlText'].replace('\n', ' '),
                'DBName': row['Schema'],
                'QueryTimeAvg': row['QueryTimeAvg'],
                'ReturnRowAvg': row['RowsSentAvg'],
                'ParseRowAvg': row['RowsExaminedAvg'],
                'Md5': row['Md5'],
                'CreateTime': self.current_time
            }
            extracted_data.append(extracted_row)
        return extracted_data

    def get_describe_user_sql_advice(self, schema, sqltext):
        """
        获取SQL优化建议
        该函数通过调用腾讯云DBBrain的DescribeUserSqlAdvice接口，为指定的SQL文本提供优化建议。
        它主要用于帮助用户提高SQL查询的性能和效率。
        参数:
        - schema (str): 数据库模式名称，用于指定要分析的数据库环境。
        - sqltext (str): 需要进行优化分析的SQL语句文本。
        返回:
        - dict: 包含SQL优化建议的字典对象，经过JSON解析以便于在Python环境中使用。
        """
        try:
            client = self._create_dbbrain_client()
            req = models.DescribeUserSqlAdviceRequest()
            params = {
                "InstanceId": self.instanceid.rds_dbinstanceid,
                "Schema": schema,
                "SqlText": sqltext,
                "Product": self.product
            }
            req.from_json_string(json.dumps(params))
            resp = client.DescribeUserSqlAdvice(req)
            return json.loads(resp.to_json_string())
        except TencentCloudSDKException as err:
            logger.error(f"Tencent Cloud SDK Exception: {err}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            raise

    def process_slow_log_results(self, schema, sqltext):
        """
        处理慢查询日志结果。
        本函数根据提供的schema和SQL文本，获取慢查询建议的描述信息，并根据这些信息生成一个结果列表。
        每条建议特别关注是否有关键（Keys）推荐，以及这些推荐是否包含SqlText。
        参数:
        - schema: 数据库架构名称。
        - sqltext: SQL查询文本。

        返回:
        - 一个字典列表，每个字典包含关于慢查询的详细信息，包括SqlText, SqlPlan, Comments, Schema, TableName, TableSchema和Keys。
        """
        result = []

        response_data = self.get_describe_user_sql_advice(schema, sqltext)
        advices_str = json.loads(response_data["Advices"])

        if advices_str:
            for advice in advices_str:
                table_name = advice.get("TableName", '')
                table_schema = advice.get("TableSchema", '')
                schema_name = response_data.get("Schema", '')
                sql_text = response_data.get("SqlText", '')
                sql_plan = str(json.loads(response_data.get("SqlPlan")).get("Before", ''))
                comments = str(json.loads(response_data.get("Comments", '')))
                tables = str(json.loads(response_data.get("Tables", '')))
                cost = str(json.loads(response_data.get("Cost")).get("After", ''))
                keys_info = advice.get("Keys", [])
                if keys_info:
                    for key in keys_info:
                        if "SqlText" in key:
                            key_sql_text = key["SqlText"]
                        elif "PossibleKeys" in key:
                            continue
                        else:
                            key_sql_text = ''
                        result.append({
                            "TableName": table_name,
                            "TableSchema": table_schema,
                            "Keys": key_sql_text,
                            "SqlText": sql_text,
                            "SqlPlan": sql_plan,
                            "Comments": comments,
                            "Tables": tables,
                            "Cost": cost,
                            "Schema": schema_name,
                        })
        return result

    def get_describe_slow_logs(self):
        """
        查看慢日志明细信息
        """
        try:
            client = self._create_dbbrain_client()
            req = models.DescribeSlowLogsRequest()
            params = {
                "Product": self.product,
                "InstanceId": self.instanceid.rds_dbinstanceid,
                "Md5": self.md5,
                "StartTime": endtime,
                "EndTime": starttime,
                "Offset": 0,
                "Limit": 100
            }
            req.from_json_string(json.dumps(params))
            resp = client.DescribeSlowLogs(req)
            return json.loads(resp.to_json_string())
        except TencentCloudSDKException as err:
            logger.error(f"Tencent Cloud SDK Exception: {err}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            raise

    def process_describe_slow_logs(self):
        """
        处理慢日志信息。
        该方法从慢日志响应中提取并处理每条慢日志的详细信息，将其转化为一个结构化的字典列表。
        每个字典代表一条慢日志，包含数据库名、锁时间、查询时间、解析行数、返回行数、SQL文本、
        执行开始时间、用户主机、主机地址、总执行次数和查询时间的95百分位数。
        Returns:
           list: 包含处理后的慢日志信息的列表。
        """
        try:
            slow_logs_response = self.get_describe_slow_logs()
            logger.info(f"慢日志明细: {slow_logs_response}")
            slow_logs = slow_logs_response.get("Rows", [])
            processed_logs = []
            for log in slow_logs:
                sql_text = log.get("SqlText", "").replace("\n", " ")
                processed_log = {
                    "DBName": log.get("Database"),
                    "LockTimes": log.get("LockTime"),
                    "QueryTimes": log.get("QueryTime"),
                    "ParseRowCounts": log.get("RowsExamined"),
                    "ReturnRowCounts": log.get("RowsSent"),
                    "SQLText": sql_text,
                    "ExecutionStartTime": log.get("Timestamp"),
                    "UserHost": log.get("UserHost"),
                    "HostAddress": log.get("UserName"),
                    "TotalExecutionCounts": "",
                    "QueryTimePct95": ""
                }
                processed_logs.append(processed_log)
            return processed_logs
        except Exception as e:
            logger.error(f"Failed to process slow logs: {e}")
            raise

    def tablespace(self, offset, limit):
        """
        获取数据库实例中表的空间使用情况。
        本方法使用腾讯云DBBrain接口，查询数据库实例中表的空间使用排名情况，并处理响应数据。
        参数:
        - offset (int): 数据偏移量，用于分页查询。
        - limit (int): 每次查询返回的数据条数，用于分页查询。
        返回:
        - result_data: 经过处理的表空间使用情况数据。
        抛出:
        - TencentCloudSDKException: 当腾讯云SDK发生异常时。
        - Exception: 其他异常情况。
        """
        try:
            client = self._create_dbbrain_client()
            req = models.DescribeTopSpaceTablesRequest()
            params = {
                "InstanceId": self.instanceid.rds_dbinstanceid,
                "Limit": self.limit,
                "SortBy": "PhysicalFileSize",
                "Product": self.product
            }
            req.from_json_string(json.dumps(params))
            resp = client.DescribeTopSpaceTables(req)
            response_data = json.loads(resp.to_json_string())
            result_data = self.process_describe_tablespace(response_data[['TopSpaceTables']])
            return result_data
        except TencentCloudSDKException as err:
            logger.error(f"Tencent Cloud SDK Exception: {err}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            raise

    def process_describe_tablespace(self, response_data):
        """
        处理数据库表空间的信息。
        该方法从数据库表空间的响应中提取并处理每张表的详细信息，将其转化为一个结构化的字典列表。
        每个字典代表一张表，包含数据库名、表名、总行数、总磁盘空间、平均每行大小、总磁盘使用率、
        磁盘使用量、磁盘使用量百分比、磁盘使用量变化量、磁盘使用量变化百分比。
        Returns:
           list: 包含处理后的数据库表空间的信息的列表。
        """
        result = []
        for item in response_data:
            table_info = {
                "table_schema": item['TableSchema'],
                "table_name": item['TableName'],
                "engine": item['Engine'],
                "total_size": item['TotalLength'],
                "table_rows": item['TableRows'],
                "data_size": item['DataLength'],
                "index_size": item['IndexLength'],
                "data_free": item['DataFree'],
                "pct_free": item['FragRatio']
            }
            result.append(table_info)
        return result
