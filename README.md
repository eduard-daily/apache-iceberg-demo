## Apache Iceberg demo(with DuckDB and Presto)
This demo project introduces an exercise with Apache Iceberg and query engines like DuckDB and Presto. The task will be divided into 4 steps:
1. Loading the 2GB .csv dataset with NYC taxi rides data from. Transforming the .csv dataset into Apache Iceberg compatible parquet format with a simple PySpark ETL script. The script will also put the transformed parquet data into the Minio bucket storage.
2. Deploying the 2 query engines: DuckDB and Presto(we will use docker environment). The query engines will be configured to work with Apache Iceberg table and Iceberg catalog(we will use file-based catalog for demo purposes).
3. Querying the same queries from both engines and comparing the execution results.
4. Analysis and observations on the performance differences between 2 engines(DuckDB and Presto).

##**Environment setup and dataset loading**

After pulling the repo, we will set up the docker environment needed for 
