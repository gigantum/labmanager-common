# LabManager Common

[![CircleCI](https://circleci.com/gh/gigantum/labmanager-common.svg?style=svg&circle-token=3cb82b88ad0817673298c4c16b57fa7ace78cd45)](https://circleci.com/gh/gigantum/labmanager-common)
[![Coverage Status](https://coveralls.io/repos/github/gigantum/labmanager-common/badge.svg?branch=integration&t=X8AMcV)](https://coveralls.io/github/gigantum/labmanager-common?branch=integration)

This repository contains common tools used across LabManager components.

## Packages

### configuration

A class for centralized configuration information is available via `lmcommon.configuration.Configuration`

The class loads configuration information found in a configuration file in this order:
    
1. Explicitly passed into the constructor
2. A file in the "installed" locations (`/etc/gigantum/labmanager.yaml`)
3. The default file in the package (`/configuration/config/labmanager.yaml.default`)

The configuration file is YAML based and should be used for all parameter storage. Parameters should be broken into 
sections based on the component.

### logging

A pre-configured logger is available from the class from lmcommon.logging.LMLogger. 

It loads logger configuration from a configuration json file in this order:

1. Explicity passed into the constructor
2. A file in the "installed" locations (`/etc/gigantum/logging.json`)
3. The default file in the package (`/logging/logging.json.default`)

If the default file is loaded, it is assumed that the log file location will not be available and a temporary file is 
automatically used.

The current configuration logs `INFO` messages and higher. If you wish to log debug messages, you must set the log level
to `DEBUG`. The python logger used is named `labmanager`.

Example usage:

```
lmlog = LMLogger().logger

lmlog.info("This is my info message")
lmlog.warning("This is my warning message")
lmlog.error("This is my error message")
```


## Testing

Tests are written using pytest. To run unit tests, simply execute pytest