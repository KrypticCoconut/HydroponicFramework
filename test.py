# SELECT
#   state      
# FROM
#   states
# WHERE
#   metadata_id = (
#     SELECT
#       metadata_id
#     FROM
#       states_meta
#     WHERE
#       entity_id = 'sensor.ph_value'
#   )
# ORDER BY
#   state_id DESC
# LIMIT
#   10;

# conn = sqlite3.connect

import subprocess