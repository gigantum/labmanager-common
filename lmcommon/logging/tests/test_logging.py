# Copyright (c) 2017 FlashX, LLC
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

import pytest
import tempfile
from unittest.mock import PropertyMock, patch
from lmcommon.logging import LMLogger
import logging
import os

@pytest.fixture(scope="module")
def mock_config_file():
    with tempfile.NamedTemporaryFile(mode="wt", suffix=".log") as log_file:
        with tempfile.NamedTemporaryFile(mode="wt") as fp:
            # Write a temporary config file
            fp.write("""{
      "version": 1,
      "loggers": {
        "labmanager": {
          "level": "INFO",
          "handlers": ["fileHandler", "consoleHandler"],
          "propagate": 0
        }
      },
      "handlers": {
        "consoleHandler": {
          "class": "logging.StreamHandler",
          "level": "CRITICAL",
          "formatter": "labmanagerFormatter",
          "stream":  "ext://sys.stdout"
        },
        "fileHandler": {
          "class": "logging.handlers.RotatingFileHandler", 
          "formatter": "labmanagerFormatter",
          "filename": "<LOGFILE>",
          "maxBytes": 2048,
          "backupCount": 20
        }
      },
      "formatters": {
        "labmanagerFormatter": {
          "format": "%(asctime)s %(levelname)-10s %(filename)s in %(funcName)s (line %(lineno)d): %(message)s"
        }
      }
    }""".replace("<LOGFILE>", log_file.name))
            fp.seek(0)

            yield fp.name  # provide the fixture value


class TestLogging(object):
    def test_init(self, mock_config_file):
        """Test loading a config file explicitly"""
        lmlog = LMLogger(mock_config_file)

        assert type(lmlog) is LMLogger
        assert lmlog.config_file is mock_config_file
        assert type(lmlog.logger) is logging.Logger

    def test_init_load_from_package(self):
        """Test loading the default file from the package"""
        lmlog = LMLogger()

        assert type(lmlog) is LMLogger

        if os.path.exists(LMLogger.CONFIG_INSTALLED_LOCATION):
            assert lmlog.config_file.rsplit("/", 1)[1] == "logging.json"
        else:
            assert lmlog.config_file.rsplit("/", 1)[1] == "logging.json.default"

        assert type(lmlog.logger) is logging.Logger

    def test_init_load_from_install(self, mock_config_file):
        """Test loading the default file from the installed location"""
        with patch('lmcommon.logging.LMLogger.CONFIG_INSTALLED_LOCATION', new_callable=PropertyMock,
                   return_value=mock_config_file):
            lmlog = LMLogger()

        assert type(lmlog) is LMLogger
        assert lmlog.config_file is mock_config_file
        assert type(lmlog.logger) is logging.Logger

    def test_log(self, mock_config_file):
        """Test logging"""
        with patch('lmcommon.logging.LMLogger.CONFIG_INSTALLED_LOCATION', new_callable=PropertyMock,
                   return_value=mock_config_file):
            lmlog = LMLogger()

        assert type(lmlog) is LMLogger
        assert lmlog.config_file is mock_config_file
        assert type(lmlog.logger) is logging.Logger

        logger = lmlog.logger

        logger.debug("##DE_BUG##")
        logger.info("##IN_FO##")
        logger.warning("##WA_RN##")
        logger.error("##ER_ROR##")

        with open(lmlog.log_file, 'rt') as test_file:
            data = test_file.readlines()

            assert "##IN_FO##" in data[0]
            assert "INFO" in data[0]
            assert "##WA_RN##" in data[1]
            assert "WARNING" in data[1]
            assert "##ER_ROR##" in data[2]
            assert "ERROR" in data[2]

    def test_load_logger_by_name(self, mock_config_file):
        """Test loading the logger by name rather than by LMLogger.logger. """
        with patch('lmcommon.logging.LMLogger.CONFIG_INSTALLED_LOCATION', new_callable=PropertyMock,
                   return_value=mock_config_file):
            lmlog = LMLogger()

        logger = logging.getLogger("labmanager")
        logger.warning('test_load_logger_by_name')

        with open(lmlog.log_file, 'rt') as test_file:
            data = test_file.readlines()

            assert any(['test_load_logger_by_name' in d for d in data])

    def test_log_exception(self, mock_config_file):
        """Test that the logging of exceptions appear as expected. """
        with patch('lmcommon.logging.LMLogger.CONFIG_INSTALLED_LOCATION', new_callable=PropertyMock,
                   return_value=mock_config_file):
            lmlog = LMLogger()

        logger = logging.getLogger("labmanager")

        try:
            1/0
        except ZeroDivisionError as e:
            logger.exception(e)

        with open(lmlog.log_file, 'rt') as test_file:
            data = test_file.readlines()

            assert any(['Traceback (most recent call last)' in d for d in data])

    def test_log_exception_using_error_to_log(self, mock_config_file):
        """Test that the logging of exceptions appear as expected. """
        with patch('lmcommon.logging.LMLogger.CONFIG_INSTALLED_LOCATION', new_callable=PropertyMock,
                   return_value=mock_config_file):
            lmlog = LMLogger()

        logger = logging.getLogger("labmanager")

        try:
            assert False
        except AssertionError as e:
            # Note, using exc_info=True additionally prints the current stack context.
            logger.error(e, exc_info=True)

        with open(lmlog.log_file, 'rt') as test_file:
            data = test_file.readlines()

            assert any(['AssertionError' in d for d in data])
            import pprint; pprint.pprint(data)
            assert False