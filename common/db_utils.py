import os
from typing import Dict, Optional

import psycopg

from common.core_utils import DEFAULT_DB_PARAMS, module_logger


def get_db_connection(
    db_params: Optional[Dict[str, str]] = None,
) -> Optional[psycopg.Connection]:
    """
    Establish and return a PostgreSQL database connection using Psycopg 3.

    Uses provided `db_params` or falls back to `DEFAULT_DB_PARAMS`
    defined in this module.

    Args:
        db_params: Optional dictionary with database connection parameters
                   (dbname, user, password, host, port).

    Returns:
        A psycopg.Connection object if successful, None otherwise.
    """
    params_to_use = DEFAULT_DB_PARAMS.copy()
    if db_params:
        params_to_use.update(db_params)

    if (
        params_to_use.get("password") == "yourStrongPasswordHere"
        and os.environ.get("PG_OSM_PASSWORD") == "yourStrongPasswordHere"
        and os.environ.get("PGPASSWORD")
        == "yourStrongPasswordHere"  # Check PGPASSWORD too
    ):
        module_logger.critical(
            "CRITICAL: Default placeholder password is being used for database "
            "connection. Please configure a strong password directly in DB_PARAMS, "
            "or via PG_OSM_PASSWORD/PGPASSWORD environment variables."
        )

    # These are standard connection string parameters
    conn_kwargs = {
        "dbname": params_to_use.get("dbname"),
        "user": params_to_use.get("user"),
        "password": params_to_use.get("password"),
        "host": params_to_use.get("host"),
        "port": params_to_use.get(
            "port"
        ),  # This is typically a string from env/defaults
    }
    # Filter out any keys that have None values
    conn_kwargs_filtered = {
        k: v for k, v in conn_kwargs.items() if v is not None
    }

    # Construct a DSN connection string
    # e.g., "dbname=gis user=osmuser host=localhost port=5432 password=xxx"
    # Values in conn_kwargs_filtered are already strings.
    dsn_parts = [
        f"{key}={value}" for key, value in conn_kwargs_filtered.items()
    ]
    conninfo_str = " ".join(dsn_parts)

    try:
        module_logger.debug(
            f"Attempting to connect to database using Psycopg 3 with DSN: '{conninfo_str}'"
        )
        # Pass the DSN string to psycopg.connect
        conn = psycopg.connect(conninfo_str)
        # Extract actual dbname, host, port for logging if possible, from the connection object itself
        # or from conn_kwargs_filtered as before, as conninfo_str might hide password for logs.
        log_db_details = {
            k: v for k, v in conn_kwargs_filtered.items() if k != "password"
        }
        module_logger.info(
            f"Connected to database {log_db_details.get('dbname', 'N/A')} on "
            f"{log_db_details.get('host', 'N/A')}:{log_db_details.get('port', 'N/A')} using Psycopg 3."
        )
        return conn
    except psycopg.OperationalError as e:  # More specific Psycopg 3 error
        module_logger.error(
            f"Psycopg 3 database connection failed (OperationalError): {e}",
            exc_info=True,
        )
    except psycopg.Error as e:  # General Psycopg 3 errors
        module_logger.error(
            f"Psycopg 3 database connection failed: {e}", exc_info=True
        )
    except Exception as e:
        module_logger.error(
            f"An unexpected error occurred while connecting to the database using Psycopg 3: {e}",
            exc_info=True,
        )
    return None
