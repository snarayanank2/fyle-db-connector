"""
FyleLoadConnector(): Connection between Fyle and Database
"""

import logging
from os import path
from typing import BinaryIO
import pandas as pd


class FyleLoadConnector:
    """
    - Extract Data from Database and load to Fyle
    """
    def __init__(self, fyle_sdk_connection, dbconn):
        self.__dbconn = dbconn
        self.__connection = fyle_sdk_connection
        self.logger = logging.getLogger(self.__class__.__name__)
        self.logger.info('Fyle connection established.')

    def create_tables(self):
        """
        Creates DB tables
        :return: None
        """
        basepath = path.dirname(__file__)
        ddl_path = path.join(basepath, 'load_ddl.sql')
        ddl_sql = open(ddl_path, 'r').read()
        self.__dbconn.executescript(ddl_sql)

    def __load_excel(self, file_path: str) -> str:
        """
        Upload Excel File to Fyle
        :param file_path: Absolute path for the excel file
        :return: returns file id
        """
        self.logger.info('Uploading excel to Fyle.')

        file_data = open(file_path, 'rb')

        file_path_tokenize = file_path.split('/')
        file_name = file_path_tokenize[len(file_path_tokenize) - 1]

        file_id = self.load_file(
            file_name,
            file_data,
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )

        self.logger.info('Excel file uploaded successfully.')
        return file_id

    def load_tpa_export_batch(self, batch_id, file_path: str = None, file_id: str = None):
        """
        Load a TPA Export Batch in Fyle
        :param batch_id: Batch ID
        :param file_path: Path of the export file
        :param file_id: Id of file already uploaded to Fyle
        :return: None
        """
        batches = pd.read_sql_query(sql=f"select * from fyle_load_tpa_export_batches where id = '{batch_id}' limit 1", con=self.__dbconn)
        if not batches:
            self.logger.info('No such batch')
            return
        if not file_id:
            if file_path:
                file_id = self.__load_excel(file_path)
            batches['file_id'] = file_id
        batches['success'] = True
        batches = batches.to_dict(orient='records')
        batch = batches[0]
        self.logger.info('Uploading batch to Fyle')

        lineitems = pd.read_sql_query(
            sql=f"select * from fyle_load_tpa_export_batch_lineitems where batch_id = '{batch_id}'",
            con=self.__dbconn
        )

        lineitems_payload = lineitems.to_dict(orient='records')

        if not lineitems_payload:
            self.logger.info('0 Lineitems. Skipping exports')
            return

        batch_id = self.__connection.Exports.post_batch(batch)['id']
        self.logger.info('Batch successfully upload. Uploading Line items.')
        self.__connection.Exports.post_batch_lineitems(batch_id, lineitems_payload)
        self.logger.info('%s Lineitems successfully uploaded.', len(lineitems_payload))

    def load_tpa_exports(self, file_path: str = None, file_id: str = None) -> None:
        """
        Load TPA Export Batches in Fyle
        :param file_path: Path of the export file
        :param file_id: Id of file already uploaded to Fyle
        :return: None
        """
        self.logger.warn('method deprecated - please use load_tpa_export_batch')

        batches_df = pd.read_sql_query(sql='select id from fyle_load_tpa_export_batches', con=self.__dbconn)
        batches = batches_df.to_dict(orient='records')

        self.logger.info('Pushing %d batches to Fyle', len(batches))

        for batch in batches:
            self.load_tpa_export_batch(batch_id=batch['id'], file_path=file_path, file_id=file_id)

    def load_file(self, file_name: str, file_data: BinaryIO, content_type: str) -> str:
        """
        Upload File to Fyle
        :param file_name: Name of the file
        :param file_data: Data of the fyle in bytes
        :param content_type: content type
        :return:
        """
        file_obj = self.__connection.Files.post(file_name)
        upload_url = self.__connection.Files.create_upload_url(file_obj['id'])['url']
        self.__connection.Files.upload_file_to_aws(content_type, file_data, upload_url)
        return file_obj['id']
