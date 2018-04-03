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
import time
import os
import socket

from lmcommon.configuration import Configuration
from lmcommon.portmap import PortMap, reset_all_ports
from lmcommon.fixtures import mock_config_file

class TestPortMap(object):
    def test_assign_and_remove(self, mock_config_file):
        """Test simple lock case"""

        config = Configuration(mock_config_file[0])
        pm = PortMap(config) 
        reset_all_ports(config)

        # allocate ports one at a time and check return
        for i in range(50):
            retval = pm.assign(f"testlabbook_{i}", '0.0.0.0',12000)
            assert(retval==12000+i)
    
        # error on the 51st port
        with pytest.raises(Exception) as e:
            pm.assign(f"testlabbook_50", '0.0.0.0',12000)

        # lookup ports
        for i in range(50):
            (iface,port) = pm.lookup(f"testlabbook_{i}")
            assert(iface=="0.0.0.0")
            assert(port==12000+i)

        # release all ports
        for i in range(50):
            pm.release(f"testlabbook_{i}") 

        # check that all ports are dealloc'ed
        prior = pm._redis_client.keys("__hostport__*")
        assert(len(prior)==0)

    def test_repeatable_allocation(self, mock_config_file):
        """Test simple lock case"""

        config = Configuration(mock_config_file[0])
        pm = PortMap(config) 
        reset_all_ports(config)

        # allocate two ports
        retval = pm.assign(f"testlabbook_13000", '0.0.0.0',13000)
        assert(retval==13000)
        retval = pm.assign(f"testlabbook_13001", '0.0.0.0',13000)
        assert(retval==13001)

        # release low port
        pm.release(f"testlabbook_{13000}") 

        # ensure low port is reassigned, i.e. not leaking ports
        retval = pm.assign(f"testlabbook_13000", '0.0.0.0',13000)
        assert(retval==13000)

        # release both
        pm.release(f"testlabbook_{13000}") 
        pm.release(f"testlabbook_{13001}") 

        # check that all ports are dealloc'ed
        prior = pm._redis_client.keys("__hostport__*")
        assert(len(prior)==0)

    def test_release_errors(self, mock_config_file):
        """Ensure that bad allocations don't work"""

        config = Configuration(mock_config_file[0])
        pm = PortMap(config) 
        reset_all_ports(config)

        # release an unallocated port
        with pytest.raises(Exception) as e:
            pm.release("labbook_10000")

        # release an active port
        with pytest.raises(Exception) as e:
            with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as s:        
                s.bind("0.0.0.0",13000)
                pm.release(13000)
                
    def test_assign_errors(self, mock_config_file):
        """Ensure that bad allocations don't work"""

        config = Configuration(mock_config_file[0])
        pm = PortMap(config) 
        reset_all_ports(config)

        # allocate a protected port
        with pytest.raises(Exception) as e:
            with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as s:        
                pm.assign("0.0.0.0",23)
