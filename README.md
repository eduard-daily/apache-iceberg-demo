## Apache Iceberg demo(with DuckDB and Presto)
This demo project introduces an exercise with Apache Iceberg and query engines like DuckDB and Presto. The task will be divided into 4 steps:
1. Loading the 2GB .csv dataset with NYC taxi rides data from [kaggle](https://www.kaggle.com/datasets/elemento/nyc-yellow-taxi-trip-data). Transforming the .csv dataset into Apache Iceberg compatible parquet format with a simple PySpark ETL script. The script will also put the transformed parquet data into the Minio bucket storage.
2. Deploying the 2 query engines: DuckDB and Presto(we will use docker environment). The query engines will be configured to work with Apache Iceberg table and Iceberg catalog(we will use file-based catalog for demo purposes).
3. Querying the same queries from both engines and comparing the execution results.
4. Analysis and observations on the performance differences between 2 engines(DuckDB and Presto).

## Environment setup and dataset loading

After pulling the repo, we will set up the docker environment needed for exersise:
```shell
$ docker compose up -d
```
We have the Minio container created along with Minio client, that created the nyc-taxi-data bucket. 
Now we need to download and put the .csv dataset into the bucket(I am using path ~/Documents/apache-iceberg-demo/ as a working folder):
```shell
$ curl -L -o ~/Downloads/nyc-yellow-taxi-trip-data.zip  https://www.kaggle.com/api/v1/datasets/download/elemento/nyc-yellow-taxi-trip-data
$ unzip ~/Downloads/nyc-yellow-taxi-trip-data.zip -d ~/Documents/apache-iceberg-demo/test_data/
$ docker exec minio ls /opt/data/yellow_tripdata_2015-01.csv
$ docker exec minio mc alias set myminio http://127.0.0.1:9000 admin password
$ docker exec minio mc cp /opt/data/yellow_tripdata_2015-01.csv myminio/nyc-taxi-data/
```
## CSV to Parquet transformation
We have added the dataset file to the freshly created bucket nyc-taxi-data.
Now we will simulate a simple ETL with a PySpark job, that will collect all of the .csv entries in the bucket, sort them, and write into created Iceberg table with a parquet files.
We are using here 2 Spark nodes: spark-master and spark-worker. In our case it's kind of an overkill and not the goal of the exercise. However, I wanted to simulate the environment, which could be somewhat similar to real life scenario.
```shell
$ docker exec spark-master spark-submit --packages org.apache.iceberg:iceberg-spark-runtime-3.3_2.12:1.2.1,org.apache.hadoop:hadoop-aws:3.3.4 /opt/spark/work-dir/csv_to_ice.py
```
## Query engines set up
Along with Minio and Spark containers, we have DuckDB(which is a normal lightweight python container) and Presto. 
### DuckDB setup
To configure the DuckDB, we will run the DuckDB executable on the container: 
```shell
$ docker exec -it duckdb /opt/duckdb/duckdb
```
To configure the DuckDB engine for communication with Iceberg table, we are setting up the needed configuration in the DuckDB shell, that was opened. Here we are installing Iceberg extention for DuckDB, setting path for Minio bucket, providing the credentials and additionally setting up a timer and output mode to box(for a nicer view):
```shell
D INSTALL iceberg;
D LOAD iceberg;
D SET s3_use_ssl=false ;
D SET s3_region = 'us-east-1';
D SET s3_url_style=path;
D SET s3_endpoint='minio:9000';
D SET s3_access_key_id='admin';
D SET s3_secret_access_key='password';
D .mode box
D .timer on
```
To verify the setup we can run a simple query:
```shell
D SELECT count(*) as all_records
  FROM iceberg_scan('s3://nyc-taxi-data/iceberg_warehouse/db/nyc_taxi_table');
┌─────────────┐
│ all_records │
├─────────────┤
│ 12748986    │
└─────────────┘

```
### Presto setup
To configure the Presto, we have the config file set: 
`apache-iceberg-demo/presto/etc`
The main part is iceberg.properties file, that contains the details about Iceberg connection.
```shell
connector.name=iceberg
iceberg.catalog.type=hadoop
iceberg.catalog.warehouse=s3a://nyc-taxi-data/iceberg_warehouse
hive.s3.path-style-access=true
hive.s3.endpoint=http://minio:9000
hive.s3.aws-access-key=admin
hive.s3.aws-secret-key=password
```
To verify the installation we will run the Presto shell, set the schema we use, and execute the same query:
```shell
docker exec -it presto-coordinator presto-cli
presto>USE "iceberg.nyc-taxi-data";
presto:iceberg.nyc-taxi-data> select count(*) as all_records from iceberg.db.nyc_taxi_table;

 all_records 
-------------
    12748986 
(1 row)
```
## Querying the data
Now we can run the same queries with 2 different engines and compare the execution time and resourse usage metrics. 
To capture the resource usage(CPU, memory, network) we will use the monitoring containers with Cadvisor, Prometheus and Grafana. To visualize the data we will import existing Grafana dashboard with ID 893.
### Querying with DuckDB
The first query: we are collecting the count of all rides with 3 passengers:
```shell
D SELECT count(*)
      FROM iceberg_scan(
          's3://nyc-taxi-data/iceberg_warehouse/db/nyc_taxi_table',
          allow_moved_paths = true
      )
    WHERE passenger_count = 3;
┌──────────────┐
│ count_star() │
├──────────────┤
│ 528486       │
└──────────────┘
Run Time (s): real 0.054 user 0.110322 sys 0.018888

```
The second query. We arecalculating average fare for a short trips(less than 5 miles) with only 1 passenger: 
```shell
D SELECT AVG(total_amount) AS avg_fare_amount 
     FROM iceberg_scan('s3://nyc-taxi-data/iceberg_warehouse/db/nyc_taxi_table')
    WHERE passenger_count = 1 AND trip_distance < 5;
┌────────────────────┐
│  avg_fare_amount   │
├────────────────────┤
│ 11.326533201474316 │
└────────────────────┘
Run Time (s): real 0.143 user 0.547267 sys 0.029865

```
The third query. This query calculates the total number of trips and the average fare amount grouped by the passenger_count.
```shell
D SELECT passenger_count, 
    COUNT(*) AS trip_count, 
    AVG(total_amount) AS avg_fare_amount 
    FROM iceberg_scan(
            's3://nyc-taxi-data/iceberg_warehouse/db/nyc_taxi_table',
            allow_moved_paths = true
        )
    GROUP BY passenger_count 
    ORDER BY passenger_count ASC;
┌─────────────────┬────────────┬────────────────────┐
│ passenger_count │ trip_count │  avg_fare_amount   │
├─────────────────┼────────────┼────────────────────┤
│ 0               │ 6565          │ 13.861300837775941 │
│ 1               │ 8993870    │ 15.111445724950782 │
│ 2               │ 1814594    │ 15.377930826347734 │
│ 3               │ 528486     │ 14.948430157104447 │
│ 4               │ 253228     │ 14.930813377668514 │
│ 5               │ 697645     │ 14.873864085618024 │
│ 6               │ 454568     │ 14.630575821451288 │
│ 7               │ 9          │ 15.181111111111111 │
│ 8               │ 10         │ 32.46399999999999  │
│ 9               │ 11         │ 62.808181818181815 │
└─────────────────┴────────────┴────────────────────┘
Run Time (s): real 0.104 user 0.297361 sys 0.024342
```
Concluding the execution time for DuckDB queries:
1. Query: 0.054 s
2. Query: 0.143 s
3. Query: 0.104 s

### Querying with Presto
We will use the exact same queries with Presto and compare the execution time results.
First query: 
```shell
presto> SELECT count(*) AS trip_count FROM iceberg.db.nyc_taxi_table WHERE passenger_count = 3;
 trip_count 
------------
     528486 
(1 row)

Query 20250114_133556_00020_h95yj, FINISHED, 1 node
Splits: 48 total, 48 done (100.00%)
[Latency: client-side: 0:01, server-side: 0:01] [12.7M rows, 6.55MB] [24.1M rows/s, 12.4MB/s]
```
Second query:
```shell
presto> SELECT AVG(total_amount) AS avg_fare_amount 
     -> FROM iceberg.db.nyc_taxi_table
     -> WHERE passenger_count = 1
     -> AND trip_distance < 5;
  avg_fare_amount   
--------------------
 11.326533201310951 
(1 row)

Query 20250114_133737_00021_h95yj, FINISHED, 1 node
Splits: 48 total, 48 done (100.00%)
[Latency: client-side: 0:01, server-side: 0:01] [12.7M rows, 54MB] [13M rows/s, 55.1MB/s]

```
Third query:
```shell
presto> SELECT passenger_count,COUNT(*) AS trip_count,AVG(total_amount) AS avg_fare_amount
     -> FROM iceberg.db.nyc_taxi_table
     -> GROUP BY passenger_count
     -> ORDER BY passenger_count ASC;
 passenger_count | trip_count |  avg_fare_amount   
-----------------+------------+--------------------
               0 |       6565 | 13.861300837776117 
               1 |    8993870 | 15.111445724650478 
               2 |    1814594 | 15.377930826408889 
               3 |     528486 |  14.94843015708747 
               4 |     253228 | 14.930813377668022 
               5 |     697645 | 14.873864085598672 
               6 |     454568 | 14.630575821437333 
               7 |          9 | 15.181111111111111 
               8 |         10 |             32.464 
               9 |         11 |  62.80818181818181 
(10 rows)

Query 20250114_133851_00022_h95yj, FINISHED, 1 node
Splits: 81 total, 81 done (100.00%)
[Latency: client-side: 0:01, server-side: 0:01] [12.7M rows, 18.7MB] [17M rows/s, 24.8MB/s]
```
To get the execution time for Presto queries:
```shell
SELECT query, state, started, "end" FROM system.runtime.queries WHERE state = 'FINISHED';
```
Presto :
1. Query: 0.332 s
2. Query: 0.601 s
3. Query: 0.547 s

## Results analysis
To conclude, during this exersice we conducted a comparison in query execution time and resourses usage between 2 search engines: DuckDBand Presto. In given conditions the DuckDB queries performed quickier and typically cost less resources. However, that does not mean, that Presto engine will always provide slower results, then DuckDB.

We can compare the resource usage results during the test in Grafana dashboard. Generally, the DuckDB container used less resources, then the Presto.
![](https://github.com/eduard-daily/apache-iceberg-demo/blob/main/ducldb_and_presto.png)
Generally we confirmed, that DuckDB excels at single-node, local analytics on small to medium datasets, offering low latency and simplicity. Presto is suitable for distributed querying of large-scale datasets across multiple sources, with scalability but higher. 
At the end, we can choose DuckDB for speed and Presto for scale and multi-source querying.

## External resources used
During the demo exercise I found some useful links, that helped me.
1. https://www.kaggle.com/datasets/elemento/nyc-yellow-taxi-trip-data - dataset used in demo.
2. https://medium.com/itversity/iceberg-catalogs-a-guide-for-data-engineers-a6190c7bf381 - good overview of Apache Iceberg catalogs.
3. https://blog.det.life/building-a-local-data-lake-from-scratch-with-minio-iceberg-spark-starrocks-mage-and-docker-c12436e6ff9d - example of Iceberg implementation with Minio.
4. https://medium.com/@wajahatullah.k/transforming-spark-dataframes-into-iceberg-tables-a-step-by-step-guide-6484e8b6b553 - PySpark and Iceberg reference.
5. https://medium.com/@Shamimw/steps-to-connect-to-presto-with-iceberg-using-hive-5cbfb4c59b1f - iceberg and Presto configuration.
6. https://habedi.medium.com/top-duckdb-cli-commands-that-you-should-know-7783af9c1fb4 - DuckDB CLI reference.
7. https://duckdb.org/docs/extensions/iceberg.html - DuckDB Iceberg integration documentation.
8. https://stackoverflow.com/questions/43999394/prometheus-how-to-monitor-other-docker-containers - Prometheus monitoring of local docker cluster.
