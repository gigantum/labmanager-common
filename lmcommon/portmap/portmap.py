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
import time
from contextlib import closing, contextmanager

from redis import StrictRedis
import redis_lock
import socket
import json
from typing import Tuple

from lmcommon.configuration import Configuration
from lmcommon.logging import LMLogger

logger = LMLogger.get_logger()


def reset_all_ports(lmconfig: Configuration) -> None:
    """ A helper method to reset all ports

    Typically used to clean things up after crashes or on startup.

    Args:
        lmconfig(dict): The configuration details for the 'lock' section of the config file

    Returns:
        None

    """
    config = lmconfig.config['lock']

    redis_client = StrictRedis(host=config['redis']['host'],
                               port=config['redis']['port'],
                               db=config['redis']['db'])

    prior = redis_client.keys("__hostport__*")
    if len(prior) != 0:
        redis_client.delete(*prior)


class PortMap(object):
    """Class to dynamically assign ports with a range"""

    def __init__(self, lmconfig: Configuration) -> None:

        self.rconfig = lmconfig.config['lock']
        self._redis_client = StrictRedis(host=self.rconfig['redis']['host'],
                                         port=self.rconfig['redis']['port'],
                                         db=self.rconfig['redis']['db'])

    @contextmanager
    def lock_hostportmap(self, lock_key: str = None):
        """A context manager for locking port assignment operations that is decorator compatible

        Manages the lock process along with catching and logging exceptions that may occur

        Args:
            lock_key(str): The lock key to override the default value.

        """
        lock: redis_lock.Lock = None

        # Create a lock key
        if not lock_key:
            lock_key = f'hostportassignment_lock'

        try:
            # Get a lock object
            lock = redis_lock.Lock(self._redis_client, lock_key,
                                   expire=self.rconfig['expire'],
                                   auto_renewal=self.rconfig['auto_renewal'],
                                   strict=self.rconfig['redis']['strict'])

            # Get the lock
            if lock.acquire(timeout=self.rconfig['timeout']):
                # Do the work
                start_time = time.time()
                yield
                if self.rconfig['expire']:
                    if (time.time() - start_time) > self.rconfig['expire']:
                        logger.warning(
                            f"Locking task took more than {self.rconfig['expire']}s. File locking possibly invalid.")

            else:
                raise IOError(f"Could not acquire host/port mapping lock within {self.rconfig['timeout']} seconds.")

        except Exception as e:
            logger.error(e)
            raise
        finally:
            # Release the Lock
            if lock:
                try:
                    lock.release()
                except redis_lock.NotAcquired as e:
                    # if you didn't get the lock and an error occurs, you probably won't be able to release, so log.
                    logger.error(e)
                    raise

    def assign(self, labbook_key: str, interface: str, desired_port: int) -> int:
        """Take a lock, claim a port, release lock, make sure it's available.
    
        Args:
            labbook_key(str) -- name under which the port should be locked (used to register for release)
            interface(str) -- the host interface (name or IP str, used in key construction)
            desired_port(int) -- port requested.  the service weill return this port or
                a higher numbered port

        Returns:
            (int) -- the port # allocated for this request.
        """
        # Lock and claim lowest available port
        with self.lock_hostportmap():
            # TODO DK/BVB -- add a number of active jplabs/rstudio processes to config 
            #  right now 50 is the hard coded number of ports to search
            for increment in range(50):
                if not self._redis_client.get(f"__hostport__{interface}__{desired_port + increment}"):

                    # verify that the port is usable
                    with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as s:
                        try:
                            s.bind((interface, desired_port + increment))
                            # if it's open, use this port
                            break
                        except socket.error as e:
                            if e.errno == 98:
                                # TODO TB improve error
                                logger.info(f"Port {desired_port+increment} occupied by foreign application.")
                            else:
                                logger.error(f"Socket raised other error {e} when attempting to allocate port {desired_port+increment}")

                if increment == 49:
                    logger.error(f"Failed to find an available port in range")
                    raise IOError("Unable to allocate port. No available ports.")

            # assign the port and register the labbook
            self._redis_client.set(f"__hostport__{interface}__{desired_port+increment}", b'1')
            self._redis_client.set(f"__hostport__labbook__{labbook_key}",
                                   json.dumps((interface, desired_port + increment)))

        return desired_port + increment

    def release(self, labbook_key: str) -> None:
        """Make sure the port is not in use and then let it go.

        Args:
            labbook_key(str) -- name under which the port should be locked (used to register for release)
        Returns:
            None
        """
        rkey = self._redis_client.get(f"__hostport__labbook__{labbook_key}")
        if rkey:
            (interface, port_number) = json.loads(rkey)
        else:
            raise IOError(f"Could not find allocated port for LabBook {labbook_key}")

        # no need to lock, it's an atomic write
        with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as s:
            try:
                s.bind((interface, port_number))
            except socket.error as e:
                if e.errno == 98:
                    logger.error(f"Trying to unassign port {port_number} that's currently in use.")
                    raise IOError(f"Port {port_number} is still bound. Cannot unregister.")
                else:
                    logger.error(f"Socket raised other error {e}")
                    raise IOError(f"Unknown socket error {e}")

        # release labbook_key first to not leave the name dangling.
        self._redis_client.delete(f"__hostport__labbook__{labbook_key}")
        self._redis_client.delete(f"__hostport__{interface}__{port_number}")

    def lookup(self, labbook_key: str) -> Tuple[str, int]:
        """
        Return the interface and port of assigned to the labbook.

        Args:
            labbook_key(str) -- name under which the port should be locked (used to register for release)
        Returns:
            str -> interface name
            int -> port number
        """
        rkey = self._redis_client.get(f"__hostport__labbook__{labbook_key}")
        if rkey:
            return json.loads(rkey)
        else:
            raise IOError(f"Could not find allocated port for LabBook {labbook_key}")
