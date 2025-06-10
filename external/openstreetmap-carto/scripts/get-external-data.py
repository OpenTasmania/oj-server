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

import argparse
import io
import logging
import os
import re
import shutil

# modules for converting and postgres loading
import subprocess

# modules for getting data
import zipfile
from urllib.parse import urlparse

import psycopg  # Changed from psycopg2
import requests
import yaml
from psycopg import sql  # Added for safe SQL identifier formatting


def database_setup(conn, temp_schema, schema, metadata_table):
    with conn.cursor() as cur:
        # Use sql.Identifier for schema names
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
    def __init__(self, name, conn, temp_schema, schema, metadata_table):
        self._name = name
        self._conn = conn
        self._temp_schema = temp_schema
        self._dst_schema = schema
        self._metadata_table = metadata_table

    # Clean up the temporary schema in preparation for loading
    def clean_temp(self):
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

    # get the last modified date from the metadata table
    def last_modified(self):
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
            # No commit needed for SELECT typically, but psycopg2 example had it.
            # In psycopg3, if a transaction was started by this SELECT (it would be, by default),
            # and nothing else is done, an explicit commit or rollback would clear it.
            # Given this function only reads, an explicit commit is harmless but often not strictly necessary
            # if the connection is managed elsewhere or if it's the end of a read-only operation.
            # However, to maintain closer behavior to the original that had a commit, keeping it is fine.
            # If no transaction was started (e.g. autocommit=True on connection), it's a no-op.
            self._conn.commit()  # Or self._conn.rollback() if it's purely read-only and no side-effects are intended.

    def grant_access(self, user_role):  # parameter renamed for clarity
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
        with self._conn.cursor() as cur:
            # Disable autovacuum while manipulating the table, since it'll get clustered towards the end.
            cur.execute(
                sql.SQL(
                    """ALTER TABLE {temp_schema}.{name} SET ( autovacuum_enabled = FALSE );"""
                ).format(
                    name=sql.Identifier(self._name),
                    temp_schema=sql.Identifier(self._temp_schema),
                )
            )

            # ogr creates a ogc_fid column we don't need
            # Add error handling in case column doesn't exist (IF EXISTS) for robustness if needed
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

            # Null geometries are useless for rendering
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

            # sorting static tables helps performance and reduces size from the column drop above
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
            )  # CLUSTER uses unquoted index name

            # The index is created within the temp_schema, so it should be dropped from there.
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

            # Reset autovacuum. The table is static, so this doesn't really
            # matter since it'll never need a vacuum.
            cur.execute(
                sql.SQL(
                    """ALTER TABLE {temp_schema}.{name} RESET ( autovacuum_enabled );"""
                ).format(
                    name=sql.Identifier(self._name),
                    temp_schema=sql.Identifier(self._temp_schema),
                )
            )
            self._conn.commit()

        # VACUUM can't be run in transaction, so autocommit needs to be turned on
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
        with self._conn.cursor() as cur:
            # Explicit BEGIN is not strictly necessary in psycopg3 if this is the start of a transaction block,
            # as a transaction will be started implicitly. However, it doesn't harm.
            # cur.execute(sql.SQL('''BEGIN;''')) # Optional

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

            # We checked if the metadata table had this table way up above
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
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "get-external-data.py/osm-carto"
        })

    def __enter__(self):
        return self

    def __exit__(self, *args, **kwargs):
        self.session.close()

    def _download(self, url, headers=None):
        if url.startswith("file://"):
            filename = url[7:]
            if headers and "If-Modified-Since" in headers:
                # Ensure comparison is between strings or handle types carefully
                # os.path.getmtime returns float
                if (
                    str(int(os.path.getmtime(filename)))
                    == headers["If-Modified-Since"]
                ):  # Basic comparison
                    return DownloadResult(
                        status_code=requests.codes.not_modified
                    )
            with open(filename, "rb") as fp:
                return DownloadResult(
                    status_code=200,
                    content=fp.read(),
                    last_modified=str(os.fstat(fp.fileno()).st_mtime),
                )  # Ensure string
        response = self.session.get(url, headers=headers)
        response.raise_for_status()
        return DownloadResult(
            status_code=response.status_code,
            content=response.content,
            last_modified=response.headers.get("Last-Modified", None),
        )

    def download(self, url, name, opts, data_dir, table_last_modified):
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
        # Variable used to tell if we downloaded something
        download_happened = False

        if opts.no_update and (cached_data or table_last_modified):
            result = cached_data
        else:
            if opts.force:
                headers = {}
            else:
                # Ensure If-Modified-Since is correctly formatted HTTP-date
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
                    # Ensure last_modified is a string before writing
                    if response.last_modified is not None:
                        with open(filename_lastmod, "w") as fp:
                            fp.write(str(response.last_modified))
                    elif os.path.exists(
                        filename_lastmod
                    ):  # if server didn't send one, remove old
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
                    result = cached_data  # Use cached data as source said not modified
                else:
                    # This case means the server reported 304 based on table_last_modified
                    # but we don't have a local cache file. The original data is in the table.
                    logging.info(
                        "  Remote data for {} not modified based on table metadata.".format(
                            name
                        )
                    )
                    # We need a DownloadResult that signifies "not modified" but has the last_modified value
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

        conn = None  # Initialize conn
        try:
            with Downloader() as d:
                # Changed psycopg2.connect to psycopg.connect
                conn = psycopg.connect(
                    database=database,
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
                    if not re.match(
                        r"""^[a-zA-Z0-9_]+$""", name
                    ):  # r'' for raw string
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

                    # Check if there is need to import
                    # A download_result.content being None can happen if status_code is 304 (Not Modified)
                    needs_import = True
                    if download_result is None:  # Download failed critically
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

                    # Ensure we have content if we decided to import
                    if (
                        download_result.content is None
                        and download_result.status_code == requests.codes.ok
                    ):
                        logging.error(
                            f"  Table {name} needs import, but download content is missing unexpectedly."
                        )
                        continue  # or raise error

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

                    # --- ogr2ogr part remains largely the same ---
                    ogrpg = f"PG:dbname='{database}'"  # Use f-string for clarity, ensure values are quoted if they can have spaces

                    if port is not None:
                        ogrpg += f" port='{port}'"
                    if user is not None:
                        ogrpg += f" user='{user}'"
                    if host is not None:
                        ogrpg += f" host='{host}'"
                    # Password should be handled carefully, often via PGPASSFILE or service file for security
                    # Including it directly in the connection string is less secure.
                    # The original script did this, so maintaining behavior.
                    if password is not None:
                        ogrpg += f" password='{password}'"

                    ogr_target_table = (
                        f"{config['settings']['temp_schema']}.{name}"
                    )

                    ogrcommand = [
                        "ogr2ogr",
                        "-f",
                        "PostgreSQL",
                        ogrpg,  # Destination datasource name
                        os.path.join(
                            workingdir, source["file"]
                        ),  # Source datasource name
                        "-lco",
                        "GEOMETRY_NAME=way",
                        "-lco",
                        "SPATIAL_INDEX=FALSE",  # We create index later
                        # '-lco', 'EXTRACT_SCHEMA_FROM_LAYER_NAME=YES', # This might conflict with -nln
                        "-nln",
                        ogr_target_table,  # Target layer name (schema.table)
                        "-overwrite",  # Overwrite if the layer exists in temp schema
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
                        # Capture stderr to a variable to include in logs if needed
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
                        if process.stderr:  # ogr2ogr often prints informational messages to stderr
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
                        # Attempt to clean up the temporary table if ogr2ogr failed mid-way
                        this_table.clean_temp()
                        raise RuntimeError(
                            "ogr2ogr error when loading table {}".format(name)
                        ) from e

                    logging.info("  Import complete")

                    this_table.index()
                    if renderuser is not None:
                        this_table.grant_access(renderuser)

                    # Use the last_modified from the downloaded data, not the table (which might be old)
                    this_table.replace(download_result.last_modified)

                    shutil.rmtree(workingdir, ignore_errors=True)
        except psycopg.Error as e:  # Catch psycopg specific errors
            logging.error(f"Database error: {e}")
            logging.error(
                f"SQL: {e.diag.sqlstate if e.diag else 'N/A'}"
            )  # More detailed error
            logging.error(
                f"Message: {e.diag.message_primary if e.diag else 'N/A'}"
            )

        except Exception as e:  # Catch other general errors
            logging.error(f"An unexpected error occurred: {e}", exc_info=True)

        finally:
            if conn:
                conn.close()
                logging.info("Database connection closed.")


if __name__ == "__main__":
    main()
