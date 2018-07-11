#!/bin/bash

AUTH_PATH=/home/circleci/project/lmcommon/auth/tests/auth_config.json

echo "{" > ${AUTH_PATH}
echo "  \"grant_type\": \"password\"," >> ${AUTH_PATH}
echo "  \"username\": \"${AUTH_TEMP_USERNAME}\"," >> ${AUTH_PATH}
echo "  \"password\": \"${AUTH_TEMP_PASSWORD}\"," >> ${AUTH_PATH}
echo "  \"audience\": \"${AUTH_TEMP_AUDIENCE}\"," >> ${AUTH_PATH}
echo "  \"client_id\": \"${AUTH_TEMP_CLIENT_ID}\"," >> ${AUTH_PATH}
echo "  \"client_secret\": \"${AUTH_TEMP_CLIENT_SECRET}\"," >> ${AUTH_PATH}
echo "  \"scope\": \"openid profile email user_metadata\"" >> ${AUTH_PATH}
echo "}" >> ${AUTH_PATH}

