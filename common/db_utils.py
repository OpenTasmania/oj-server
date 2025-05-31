import os
from typing import Optional, Dict

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
            and os.environ.get("PGPASSWORD") == "yourStrongPasswordHere"  # Check PGPASSWORD too
    ):
        module_logger.critical(
            "CRITICAL: Default placeholder password is being used for database "
            "connection. Please configure a strong password directly in DB_PARAMS, "
            "or via PG_OSM_PASSWORD/PGPASSWORD environment variables."
        )

    conn_kwargs = {
        "dbname": params_to_use.get("dbname"),
        "user": params_to_use.get("user"),
        "password": params_to_use.get("password"),
        "host": params_to_use.get("host"),
        "port": params_to_use.get("port"),
    }
    conn_kwargs_filtered = {k: v for k, v in conn_kwargs.items() if v is not None}

    try:
        module_logger.debug(
            f"Attempting to connect to database using Psycopg 3: "
            f"dbname='{conn_kwargs_filtered.get('dbname')}', "
            f"user='{conn_kwargs_filtered.get('user')}', "
            f"host='{conn_kwargs_filtered.get('host')}', "
            f"port='{conn_kwargs_filtered.get('port')}'"
        )
        conn = psycopg.connect(**conn_kwargs_filtered)
        module_logger.info(
            f"Connected to database {conn_kwargs_filtered.get('dbname')} on "
            f"{conn_kwargs_filtered.get('host')}:{conn_kwargs_filtered.get('port')} using Psycopg 3."
        )
        return conn
    except psycopg.OperationalError as e:  # More specific Psycopg 3 error
        module_logger.error(f"Psycopg 3 database connection failed (OperationalError): {e}", exc_info=True)
    except psycopg.Error as e:  # General Psycopg 3 errors
        module_logger.error(f"Psycopg 3 database connection failed: {e}", exc_info=True)
    except Exception as e:
        module_logger.error(
            f"An unexpected error occurred while connecting to the database using Psycopg 3: {e}",
            exc_info=True,
        )
    return None
