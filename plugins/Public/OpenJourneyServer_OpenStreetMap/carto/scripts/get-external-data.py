#!/usr/bin/env python3
"""This script is designed to load quasi-static data into a PostGIS database
for rendering maps. It differs from the usual scripts to do this in that it is
designed to take its configuration from a file rather than be a series of shell
commands.

Some implicit assumptions are
- Time spent querying (rendering) the data is more valuable than the one-time
  cost of loading it
- The script will not be running multiple times in parallel. This is not
  normally likely because the script is likely to be called daily or less,
  not minutely.
- Usage patterns will be similar to typical map rendering
"""

# Psycopg(3) version
# NOTE: The orginal version of this script is:
# https://raw.githubusercontent.com/gravitystorm/openstreetmap-carto/refs/heads/master/scripts/get-external-data.py

import argparse
import io
import logging
import os
import re
import shutil
import subprocess
import zipfile
from urllib.parse import urlparse

import psycopg
import requests
import yaml
from psycopg import sql


def database_setup(conn, temp_schema, schema, metadata_table):
    """
    Sets up the database by creating a temporary schema and a metadata table.
    If the schema or table already exists, they will not be duplicated.
    This function ensures the necessary structures are in place for further operations.

    Arguments:
        conn: Connection
            A database connection object used to execute SQL statements.
        temp_schema: str
            The name of the temporary schema to create if it does not already exist.
        schema: str
            The name of the schema where the metadata table will reside.
        metadata_table: str
            The name of the metadata table to create within the specified schema.

    Raises:
        No specific errors are raised explicitly by this function, but errors from
        the database such as connection issues or SQL execution errors might propagate.

    """
    with conn.cursor() as cur:
        cur.execute(
            sql.SQL("""CREATE SCHEMA IF NOT EXISTS {temp_schema};""").format(
                temp_schema=sql.Identifier(temp_schema)
            )
        )
        cur.execute(
            sql.SQL(
                """CREATE TABLE IF NOT EXISTS {schema}.{metadata_table}
                   (
                       name
                       text
                       primary
                       key,
                       last_modified
                       text
                   );"""
            ).format(
                schema=sql.Identifier(schema),
                metadata_table=sql.Identifier(metadata_table),
            )
        )
    conn.commit()


class Table:
    """
    Represents a database table and provides utilities for managing it.

    This class allows the user to perform operations such as cleaning temporary tables,
    fetching the timestamp of the last modification, granting access to a role, indexing
    tables, and replacing tables within a database schema. It facilitates interaction
    with the database using SQL commands and ensures that changes are applied and committed
    appropriately.

    Attributes:
        _name (str): The name of the table.
        _conn: The database connection object.
        _temp_schema (str): The schema in the database associated with temporary tables.
        _dst_schema (str): The schema in the database where the table resides.
        _metadata_table (str): The name of the metadata table used for tracking.

    """

    def __init__(self, name, conn, temp_schema, schema, metadata_table):
        """
        Initializes an instance of the class with the provided parameters and sets up
        the instance variables for use in further operations.

        Args:
            name (str): The name associated with the instance.
            conn: The connection object to interact with the database.
            temp_schema (str): The name of the temporary schema to be used.
            schema (str): The destination schema for operations.
            metadata_table (str): The name of the metadata table to use.

        """
        self._name = name
        self._conn = conn
        self._temp_schema = temp_schema
        self._dst_schema = schema
        self._metadata_table = metadata_table

    def clean_temp(self):
        """
        Drops a temporary table in the specified schema if it exists.

        This method executes an SQL command to drop a temporary table in a
        given schema using a database connection. The method commits the
        transaction after executing the SQL command.

        Raises:
            Any exceptions that may occur during the execution of the SQL query
            or committing the transaction.
        """
        with self._conn.cursor() as cur:
            cur.execute(
                sql.SQL(
                    """DROP TABLE IF EXISTS {temp_schema}.{name}"""
                ).format(
                    name=sql.Identifier(self._name),
                    temp_schema=sql.Identifier(self._temp_schema),
                )
            )
            self._conn.commit()

    def last_modified(self):
        """
        Fetches the last modified timestamp for a specific record in the metadata table.

        This method retrieves the last modified timestamp of an entry in the specified
        metadata table within the given schema. If no entry is found for the specified
        name, it commits the current transaction and returns None.

        Returns:
            datetime: The timestamp of the last modification if found, otherwise None.
        """
        with self._conn.cursor() as cur:
            cur.execute(
                sql.SQL(
                    """SELECT last_modified
                       FROM {schema}.{metadata_table}
                       WHERE name = %s"""
                ).format(
                    schema=sql.Identifier(self._dst_schema),
                    metadata_table=sql.Identifier(self._metadata_table),
                ),
                [self._name],
            )
            results = cur.fetchone()
            if results is not None:
                return results[0]

            self._conn.commit()
            return None

    def grant_access(self, user_role):
        """
        Grants SELECT permissions on a specified database schema and table to a user role.
        This method executes a SQL statement to provide access to the table, defined
        by the instance, within a temporary schema for the specified user role.

        Args:
            user_role (str): The name of the database user role to which SELECT
                permissions are to be granted.

        Raises:
            psycopg2.Error: If there is an issue executing the SQL command or
                committing the transaction.
        """
        with self._conn.cursor() as cur:
            cur.execute(
                sql.SQL(
                    """GRANT SELECT ON {temp_schema}.{name} TO {role};"""
                ).format(
                    name=sql.Identifier(self._name),
                    temp_schema=sql.Identifier(self._temp_schema),
                    role=sql.Identifier(user_role),
                )
            )
            self._conn.commit()

    def index(self):
        """
        Executes a sequence of SQL operations on a given table within a specified schema to modify
        its structure and optimize its performance. The operations include disabling autovacuum,
        dropping an unnecessary column (if it exists), deleting rows with NULL values in a specific
        column, setting constraints, creating and deleting indices, clustering, and vacuuming the
        target table.

        Attributes:
            _conn (psycopg.Connection): The database connection object used to execute SQL queries.
            _name (str): The name of the target table being modified and optimized.
            _temp_schema (str): The name of the schema in which the target table resides.

        Raises:
            psycopg.errors.UndefinedColumn: If the specified column to drop does not exist in the
            target table, this is caught and logged as a warning.

        """
        with self._conn.cursor() as cur:
            cur.execute(
                sql.SQL(
                    """ALTER TABLE {temp_schema}.{name} SET ( autovacuum_enabled = FALSE );"""
                ).format(
                    name=sql.Identifier(self._name),
                    temp_schema=sql.Identifier(self._temp_schema),
                )
            )

            try:
                cur.execute(
                    sql.SQL(
                        """ALTER TABLE {temp_schema}.{name} DROP COLUMN ogc_fid;"""
                    ).format(
                        name=sql.Identifier(self._name),
                        temp_schema=sql.Identifier(self._temp_schema),
                    )
                )
            except psycopg.errors.UndefinedColumn:
                logging.warning(
                    f"Column ogc_fid not found on table {self._temp_schema}.{self._name}, skipping drop."
                )

            cur.execute(
                sql.SQL(
                    """DELETE
                       FROM {temp_schema}.{name}
                       WHERE way IS NULL;"""
                ).format(
                    name=sql.Identifier(self._name),
                    temp_schema=sql.Identifier(self._temp_schema),
                )
            )
            cur.execute(
                sql.SQL(
                    """ALTER TABLE {temp_schema}.{name} ALTER COLUMN way SET NOT NULL;"""
                ).format(
                    name=sql.Identifier(self._name),
                    temp_schema=sql.Identifier(self._temp_schema),
                )
            )

            idx_name = self._name + "_order"

            cur.execute(
                sql.SQL(
                    """CREATE INDEX {index_identifier} ON {temp_schema}.{name} (ST_Envelope(way));"""
                ).format(
                    index_identifier=sql.Identifier(idx_name),
                    name=sql.Identifier(self._name),
                    temp_schema=sql.Identifier(self._temp_schema),
                )
            )

            cur.execute(
                sql.SQL(
                    """CLUSTER {temp_schema}.{name} USING {index_identifier};"""
                ).format(
                    name=sql.Identifier(self._name),
                    temp_schema=sql.Identifier(self._temp_schema),
                    index_identifier=sql.Identifier(idx_name),
                )
            )

            cur.execute(
                sql.SQL(
                    """DROP INDEX {temp_schema}.{index_identifier};"""
                ).format(
                    temp_schema=sql.Identifier(self._temp_schema),
                    index_identifier=sql.Identifier(idx_name),
                )
            )

            cur.execute(
                sql.SQL(
                    """CREATE INDEX ON {temp_schema}.{name} USING GIST (way) WITH (fillfactor=100);"""
                ).format(
                    name=sql.Identifier(self._name),
                    temp_schema=sql.Identifier(self._temp_schema),
                )
            )

            cur.execute(
                sql.SQL(
                    """ALTER TABLE {temp_schema}.{name} RESET ( autovacuum_enabled );"""
                ).format(
                    name=sql.Identifier(self._name),
                    temp_schema=sql.Identifier(self._temp_schema),
                )
            )
            self._conn.commit()

        old_autocommit = self._conn.autocommit
        try:
            self._conn.autocommit = True
            with self._conn.cursor() as cur:
                cur.execute(
                    sql.SQL(
                        """VACUUM ANALYZE {temp_schema}.{name};"""
                    ).format(
                        name=sql.Identifier(self._name),
                        temp_schema=sql.Identifier(self._temp_schema),
                    )
                )
        finally:
            self._conn.autocommit = old_autocommit

    def replace(self, new_last_modified):
        """
        Replaces an existing table by moving a temporary table to the destination schema.
        Updates or inserts metadata information of the replaced table in a metadata table.

        Args:
            new_last_modified (str): A string representing the new last modified timestamp
                for the replaced table.

        Raises:
            psycopg2.DatabaseError: If there are issues executing the SQL commands.
        """
        with self._conn.cursor() as cur:
            cur.execute(
                sql.SQL("""DROP TABLE IF EXISTS {schema}.{name};""").format(
                    name=sql.Identifier(self._name),
                    schema=sql.Identifier(self._dst_schema),
                )
            )
            cur.execute(
                sql.SQL(
                    """ALTER TABLE {temp_schema}.{name} SET SCHEMA {schema};"""
                ).format(
                    name=sql.Identifier(self._name),
                    temp_schema=sql.Identifier(self._temp_schema),
                    schema=sql.Identifier(self._dst_schema),
                )
            )

            cur.execute(
                sql.SQL(
                    """SELECT 1
                       FROM {schema}.{metadata_table}
                       WHERE name = %s"""
                ).format(
                    schema=sql.Identifier(self._dst_schema),
                    metadata_table=sql.Identifier(self._metadata_table),
                ),
                [self._name],
            )

            if cur.rowcount == 0:
                cur.execute(
                    sql.SQL(
                        """INSERT INTO {schema}.{metadata_table}
                               (name, last_modified)
                           VALUES (%s, %s)"""
                    ).format(
                        schema=sql.Identifier(self._dst_schema),
                        metadata_table=sql.Identifier(self._metadata_table),
                    ),
                    [self._name, new_last_modified],
                )
            else:
                cur.execute(
                    sql.SQL(
                        """UPDATE {schema}.{metadata_table}
                           SET last_modified = %s
                           WHERE name = %s"""
                    ).format(
                        schema=sql.Identifier(self._dst_schema),
                        metadata_table=sql.Identifier(self._metadata_table),
                    ),
                    [new_last_modified, self._name],
                )
        self._conn.commit()


class Downloader:
    """
    Downloader class is responsible for HTTP file downloads and local caching.

    Provides functionality for fetching remote resources while optionally caching
    files locally. Supports HTTP headers like 'If-Modified-Since' to optimize
    requests by avoiding re-downloads if a local cached copy is up-to-date. Offers
    support for handling cached files and metadata and includes cleanup mechanisms.

    Attributes:
        session: An instance of requests.Session, initialized with custom headers
                 for User-Agent to identify downloader usage.

    Methods:
        __enter__: Manages initialization for context manager support.
        __exit__: Closes the session when exiting the context.
        _download: Handles downloading resources from either HTTP or local file
                   sources. Headers can be provided for conditional requests.
        download: Manages downloading with caching logic, supporting options such
                  as forced updates, cache usage, and deletion of outdated cache.
    """

    def __init__(self):
        """
        This class handles initialization of an HTTP session with custom headers
        to be used for making HTTP requests. It is configured to include a specific
        User-Agent string in its requests.

        Attributes:
            session (requests.Session): An instance of the requests.Session class
            used to manage HTTP session settings and handle requests.

        """
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "get-external-data.py/osm-carto"
        })

    def __enter__(self):
        """
        Provides the context management setup for the object, enabling support for
        the `with` statement. This method is invoked automatically when the object
        is used as the context expression in a `with` block.

        Returns:
            The object instance itself, to be used as the context manager.
        """
        return self

    def __exit__(self, *args, **kwargs):
        """
        Closes the session when exiting a context.

        This method is intended to be used for cleanup purposes when exiting a context
        manager. It ensures the session associated with the object is properly closed.

        Args:
            *args: Optional positional arguments provided to the context manager's
                exit handling.
            **kwargs: Optional keyword arguments provided to the context manager's
                exit handling.
        """
        self.session.close()

    def _download(self, url, headers=None):
        """
        Downloads content from a given URL or file path. The method distinguishes between
        file URLs starting with "file://" and other URLs, handling them differently. For
        file URLs, it reads the content directly from the local file system, optionally
        checking for modification timestamps. For non-file URLs, the method performs
        an HTTP GET request using the provided headers.

        Parameters:
            url (str): The URL or file path to download content from. For local files,
            the URL should start with "file://".
            headers (Optional[dict]): Optional headers to be included in the HTTP request.
            If provided, may include the "If-Modified-Since" header for timestamp-based
            conditional requests.

        Returns:
            DownloadResult: A named tuple that contains:
                - status_code (int): The HTTP status code or equivalent status for local
                  file operations (e.g., requests.codes.not_modified for unmodified files).
                - content (bytes): The downloaded content in bytes format.
                - last_modified (Optional[str]): The last modification timestamp of the
                  resource, represented as a string. For local files, it reflects the
                  modification time of the file; for HTTP responses, it corresponds to
                  the "Last-Modified" header.

        Raises:
            requests.exceptions.HTTPError: If the HTTP GET request encounters an error
            (e.g., unreachable URL, failed response).
        """
        if url.startswith("file://"):
            filename = url[7:]
            if headers and "If-Modified-Since" in headers:
                if (
                    str(int(os.path.getmtime(filename)))
                    == headers["If-Modified-Since"]
                ):
                    return DownloadResult(
                        status_code=requests.codes.not_modified
                    )
            with open(filename, "rb") as fp:
                return DownloadResult(
                    status_code=200,
                    content=fp.read(),
                    last_modified=str(os.fstat(fp.fileno()).st_mtime),
                )
        response = self.session.get(url, headers=headers)
        response.raise_for_status()
        return DownloadResult(
            status_code=response.status_code,
            content=response.content,
            last_modified=response.headers.get("Last-Modified", None),
        )

    def download(self, url, name, opts, data_dir, table_last_modified):
        """
        Downloads a file from a specified URL, implements caching, and manages conditional requests.
        The function checks for cached versions of the file and updates it only if necessary based on
        HTTP headers or options provided. It supports cache deletion, conditional GET requests using
        'If-Modified-Since' headers, and logs the download process.

        Parameters:
        url (str): The URL of the file to download.
        name (str): A descriptive name of the file, mainly for logging purposes.
        opts (Options): An object containing options like no_update, force, cache, and delete_cache.
        data_dir (str): The local directory path where the file cache is stored.
        table_last_modified (str | None): Optional HTTP 'Last-Modified' date of the table data for conditional requests.

        Returns:
        DownloadResult | None: A DownloadResult object containing the status code, file content, and last modified
        information if the download is successful or cached data is used. Returns None if the download fails
        or no content is retrieved.
        """
        filename = os.path.join(
            data_dir, os.path.basename(urlparse(url).path)
        )
        filename_lastmod = filename + ".lastmod"
        if os.path.exists(filename) and os.path.exists(filename_lastmod):
            with open(filename_lastmod, "r") as fp:
                lastmod_cache = fp.read()
            with open(filename, "rb") as fp:
                cached_data = DownloadResult(
                    status_code=200,
                    content=fp.read(),
                    last_modified=lastmod_cache,
                )
        else:
            cached_data = None
            lastmod_cache = None

        result = None
        download_happened = False

        if opts.no_update and (cached_data or table_last_modified):
            result = cached_data
        else:
            if opts.force:
                headers = {}
            else:
                # TODO: Ensure If-Modified-Since is correctly formatted HTTP-date
                # table_last_modified and lastmod_cache might need parsing/reformatting if not already HTTP-date strings
                # For simplicity, assuming they are either None or valid HTTP-date strings
                headers = {
                    "If-Modified-Since": table_last_modified or lastmod_cache
                }
                if headers["If-Modified-Since"] is None:
                    del headers["If-Modified-Since"]

            response = self._download(url, headers)
            if response.status_code == requests.codes.ok:
                logging.info(
                    "  Download complete ({} bytes)".format(
                        len(response.content)
                    )
                )
                download_happened = True
                if opts.cache:
                    with open(filename, "wb") as fp:
                        fp.write(response.content)
                    if response.last_modified is not None:
                        with open(filename_lastmod, "w") as fp:
                            fp.write(str(response.last_modified))
                    elif os.path.exists(filename_lastmod):
                        os.remove(filename_lastmod)

                result = response
            elif response.status_code == requests.codes.not_modified:
                if os.path.exists(filename) and os.path.exists(
                    filename_lastmod
                ):
                    logging.info(
                        "  Cached file {} did not require updating".format(
                            url
                        )
                    )
                    result = cached_data
                else:
                    logging.info(
                        "  Remote data for {} not modified based on table metadata.".format(
                            name
                        )
                    )
                    result = DownloadResult(
                        status_code=requests.codes.not_modified,
                        last_modified=table_last_modified,
                    )
            else:
                logging.critical(
                    "  Unexpected response code ({}".format(
                        response.status_code
                    )
                )
                logging.critical(
                    "  Content {} was not downloaded".format(name)
                )
                return None

        if opts.delete_cache or (not opts.cache and download_happened):
            try:
                os.remove(filename)
                os.remove(filename_lastmod)
            except FileNotFoundError:
                pass

        return result


class DownloadResult:
    """
    Represents the result of a download operation.

    This class encapsulates the details of a download operation, including the
    HTTP status code, the downloaded content (if available), and the last modified
    timestamp of the resource (if applicable). It provides a structured way to
    store and access these details.
    """

    def __init__(self, status_code, content=None, last_modified=None):
        self.status_code = status_code
        self.content = content
        self.last_modified = last_modified


def main():
    parser = argparse.ArgumentParser(
        description="Load external data into a database"
    )

    parser.add_argument(
        "-f",
        "--force",
        action="store_true",
        help="Download and import new data, even if not required.",
    )
    parser.add_argument(
        "-C",
        "--cache",
        action="store_true",
        help="Cache downloaded data. Useful if you'll have your database volume deleted in the future",
    )
    parser.add_argument(
        "--no-update",
        action="store_true",
        help="Don't download newer data than what is locally available (either in cache or table). Overridden by --force",
    )

    parser.add_argument(
        "--delete-cache",
        action="store_true",
        help="Execute as usual, but delete cached data",
    )
    parser.add_argument(
        "--force-import",
        action="store_true",
        help="Import data into table even if may not be needed",
    )

    parser.add_argument(
        "-c",
        "--config",
        action="store",
        default="external-data.yml",
        help="Name of configuration file (default external-data.yml)",
    )
    parser.add_argument(
        "-D",
        "--data",
        action="store",
        help="Override data download directory",
    )

    parser.add_argument(
        "-d",
        "--database",
        action="store",
        help="Override database name to connect to",
    )
    parser.add_argument(
        "-H",
        "--host",
        action="store",
        help="Override database server host or socket directory",
    )
    parser.add_argument(
        "-p", "--port", action="store", help="Override database server port"
    )
    parser.add_argument(
        "-U", "--username", action="store", help="Override database user name"
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Be more verbose. Overrides -q",
    )
    parser.add_argument(
        "-q",
        "--quiet",
        action="store_true",
        help="Only report serious problems",
    )
    parser.add_argument(
        "-w", "--password", action="store", help="Override database password"
    )

    parser.add_argument(
        "-R",
        "--renderuser",
        action="store",
        help="User to grant access for rendering",
    )

    opts = parser.parse_args()

    if opts.verbose:
        logging.basicConfig(
            format="%(levelname)s: %(message)s", level=logging.DEBUG
        )
    elif opts.quiet:
        logging.basicConfig(
            format="%(levelname)s: %(messages)s", level=logging.WARNING
        )
    else:
        logging.basicConfig(
            format="%(levelname)s: %(message)s", level=logging.INFO
        )

    if opts.force and opts.no_update:
        opts.no_update = False
        logging.warning("Force (-f) flag overrides --no-update flag")

    logging.info("Starting load of external data into database")

    with open(opts.config) as config_file:
        config = yaml.safe_load(config_file)
        data_dir = opts.data or config["settings"]["data_dir"]
        os.makedirs(data_dir, exist_ok=True)

        database = opts.database or config["settings"].get("database")
        host = opts.host or config["settings"].get("host")
        port = opts.port or config["settings"].get("port")
        user = opts.username or config["settings"].get("username")
        password = opts.password or config["settings"].get("password")

        renderuser = opts.renderuser or config["settings"].get("renderuser")

        conn = None
        try:
            with Downloader() as d:
                conn = psycopg.connect(
                    dbname=database,
                    host=host,
                    port=port,
                    user=user,
                    password=password,
                )

                database_setup(
                    conn,
                    config["settings"]["temp_schema"],
                    config["settings"]["schema"],
                    config["settings"]["metadata_table"],
                )

                for name, source in config["sources"].items():
                    logging.info("Checking table {}".format(name))
                    if not re.match(r"""^[a-zA-Z0-9_]+$""", name):
                        raise RuntimeError(
                            "Only ASCII alphanumeric table are names supported"
                        )

                    this_table = Table(
                        name,
                        conn,
                        config["settings"]["temp_schema"],
                        config["settings"]["schema"],
                        config["settings"]["metadata_table"],
                    )
                    this_table.clean_temp()

                    table_lm = this_table.last_modified()
                    download_result = d.download(
                        source["url"], name, opts, data_dir, table_lm
                    )

                    needs_import = True
                    if download_result is None:
                        logging.warning(
                            f"  Skipping import for table {name} due to download failure."
                        )
                        needs_import = False
                    elif (
                        download_result.status_code
                        == requests.codes.not_modified
                    ):
                        logging.info(
                            f"  Data for table {name} is not modified. Current LMT: {download_result.last_modified}"
                        )
                        if opts.force or opts.force_import:
                            logging.info(
                                f"  Force importing table {name} despite no modification."
                            )
                        else:
                            needs_import = False
                    elif (
                        not opts.force
                        and not opts.force_import
                        and table_lm == download_result.last_modified
                    ):
                        logging.info(
                            f"  Table {name} (LMT: {table_lm}) matches download (LMT: {download_result.last_modified}). No update needed."
                        )
                        needs_import = False

                    if not needs_import:
                        continue

                    if (
                        download_result.content is None
                        and download_result.status_code == requests.codes.ok
                    ):
                        logging.error(
                            f"  Table {name} needs import, but download content is missing unexpectedly."
                        )
                        raise

                    logging.info(
                        f"  Proceeding with import for table {name}."
                    )
                    workingdir = os.path.join(data_dir, name)
                    shutil.rmtree(workingdir, ignore_errors=True)
                    os.makedirs(workingdir, exist_ok=True)

                    if (
                        "archive" in source
                        and source["archive"]["format"] == "zip"
                    ):
                        logging.info("  Decompressing file")
                        if download_result.content is None:
                            logging.error(
                                f"  Cannot decompress {name}: download content is missing."
                            )
                            continue
                        zip_file = zipfile.ZipFile(
                            io.BytesIO(download_result.content)
                        )
                        for member in source["archive"]["files"]:
                            zip_file.extract(member, workingdir)

                    ogrpg = f"PG:dbname='{database}'"

                    if port is not None:
                        ogrpg += f" port='{port}'"
                    if user is not None:
                        ogrpg += f" user='{user}'"
                    if host is not None:
                        ogrpg += f" host='{host}'"
                    # TODO: Fix
                    # Password should be handled carefully, often via PGPASSFILE or service file for security
                    # Including it directly in the connection string is less secure.
                    # The original script did this, so maintaining behavior.
                    if password is not None:
                        ogrpg += f" password='{password}'"

                    ogr_target_table = (
                        f"{config['settings']['temp_schema']}.{name}"
                    )
                    # TODO: Address ogr2ogr warnings.
                    # The superuser privilege warning for ogr_system_tables_event_trigger_for_metadata needs to be considered.
                    ogrcommand = [
                        "ogr2ogr",
                        "-f",
                        "PostgreSQL",
                        ogrpg,
                        os.path.join(workingdir, source["file"]),
                        "-lco",
                        "GEOMETRY_NAME=way",
                        "-lco",
                        "SPATIAL_INDEX=NONE",
                        "-nln",
                        ogr_target_table,
                        "-overwrite",
                    ]

                    if "ogropts" in source:
                        ogrcommand += source["ogropts"]

                    logging.info("  Importing into database using ogr2ogr")
                    logging.debug(
                        "running {}".format(
                            subprocess.list2cmdline(ogrcommand)
                        )
                    )

                    try:
                        process = subprocess.run(
                            ogrcommand,
                            capture_output=True,
                            text=True,
                            check=True,
                        )
                        if process.stdout:
                            logging.debug(
                                f"ogr2ogr stdout:\n{process.stdout}"
                            )
                        if process.stderr:
                            logging.info(f"ogr2ogr stderr:\n{process.stderr}")
                    except subprocess.CalledProcessError as e:
                        logging.critical(
                            "ogr2ogr returned {} with layer {}".format(
                                e.returncode, name
                            )
                        )
                        logging.critical(
                            "Command line was {}".format(
                                subprocess.list2cmdline(e.cmd)
                            )
                        )
                        if e.stdout:
                            logging.critical(
                                "Output was\n{}".format(e.stdout)
                            )
                        if e.stderr:
                            logging.critical("Error was\n{}".format(e.stderr))
                        this_table.clean_temp()
                        raise RuntimeError(
                            "ogr2ogr error when loading table {}".format(name)
                        ) from e

                    logging.info("  Import complete")

                    this_table.index()
                    if renderuser is not None:
                        this_table.grant_access(renderuser)

                    this_table.replace(download_result.last_modified)

                    shutil.rmtree(workingdir, ignore_errors=True)
        except psycopg.Error as e:
            logging.error(f"Database error: {e}")
            logging.error(f"SQL: {e.diag.sqlstate if e.diag else 'N/A'}")
            logging.error(
                f"Message: {e.diag.message_primary if e.diag else 'N/A'}"
            )
            raise

        except Exception as e:
            logging.error(f"An unexpected error occurred: {e}", exc_info=True)
            raise
        finally:
            if conn:
                conn.close()
                logging.info("Database connection closed.")


if __name__ == "__main__":
    main()
