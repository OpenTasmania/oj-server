## `osm2pgsql` Command-Line Optimisation

Based on suggestions from [this Crunchydata post](https://www.crunchydata.com/blog/loading-the-world-openstreetmap-import-in-under-4-hours).

Tune Your Instrument

First, we are using bare metal hardware—a server with 128GB RAM—so so let’s tune Postgres for loading and to match that
server:

```
max_wal_size = 256GB
shared_buffers = 48GB
effective_cache_size = 64GB
maintenance_work_mem = 20GB
work_mem = 1GB
```

Second, let’s prioritize bulk load. The following settings do not make sense for a live system under read/write load,
but they will improve performance for this bulk load scenario:

```checkpoint_timeout = 60min
synchronous_commit = off
# if you don't have replication:
wal_level = minimal
max_wal_senders = 0
# if you believe my testing these make things
# faster too
fsync = off
autovacuum = off
full_page_writes = off
```

Based on suggestions
from [this Stack Overflow answer](https://stackoverflow.com/questions/56517589/osm2pgsql-import-speed-is-slow-at-ways).

* **Memory Cache (`-C`)**: Try lowering the cache size to around `4096` if you have limited memory for both PostgreSQL
  and the `osm2pgsql` process.
* **Flat Nodes (`--flat-nodes`)**: Use `--flat-nodes /tmp/mycache.bin` to speed up processing by using a local file for
  temporary node storage instead of the database.
* **Unlogged Tables (`--unlogged`)**: Consider using `--unlogged` for faster imports, but be sure to read the
  documentation to understand the risks and consequences (e.g., data is not written to the write-ahead log).

## Cloud Environment Strategy

For cloud environments like AWS, consider using a higher-performance machine for the initial data loading and then
scaling down for regular operation.

* **Loading**: Use a compute-optimised instance like an `r5a.2xlarge`.
* **Serving**: Scale down to a more cost-effective instance like a `t3.medium`.
* **Containerisation**: You can also use container hosts like AWS Fargate for processing, so you only pay while the
  import or updates are running.

## Personal Configuration & Benchmarks

Here is my current configuration and some performance notes on a 64GB memory machine.

**Command:**