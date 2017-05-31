# LabManager Common
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


## Testing

Tests are written using pytest. To run unit tests, simply execute pytest