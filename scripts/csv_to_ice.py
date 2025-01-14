from pyspark.sql import SparkSession
from pyspark.sql.functions import col, date_format

spark = SparkSession.builder \
    .appName("CSV to Iceberg") \
    .config("spark.hadoop.fs.s3a.endpoint", "http://minio:9000") \
    .config("spark.hadoop.fs.s3a.access.key", "admin") \
    .config("spark.hadoop.fs.s3a.secret.key", "password") \
    .config("spark.hadoop.fs.s3a.path.style.access", "true") \
    .config("spark.hadoop.fs.s3a.impl", "org.apache.hadoop.fs.s3a.S3AFileSystem") \
    .config("spark.sql.catalog.taxi_catalog", "org.apache.iceberg.spark.SparkCatalog") \
    .config("spark.sql.catalog.taxi_catalog.type", "hadoop") \
    .config("spark.sql.catalog.taxi_catalog.warehouse", "s3a://nyc-taxi-data/iceberg_warehouse") \
    .getOrCreate()

#reading the .csv dataset
df = spark.read.csv("s3a://nyc-taxi-data/*tripdata*.csv", header=True, inferSchema=True)

df = df.withColumn("tpep_pickup_datetime", col("tpep_pickup_datetime").cast("timestamp")) \
       .withColumn("tpep_dropoff_datetime", col("tpep_dropoff_datetime").cast("timestamp")) \
       .withColumn("trip_distance", col("trip_distance").cast("double")) \
       .withColumn("passenger_count", col("passenger_count").cast("int"))

# adding a partition "pickup_date" field for easier navigation
df = df.withColumn("pickup_date", date_format(col("tpep_pickup_datetime"), "yyyy-MM-dd"))

df = df.sort("VendorID", "pickup_date")

#declaring the new iceberg table
spark.sql("""
    CREATE TABLE IF NOT EXISTS taxi_catalog.db.nyc_taxi_table (
        VendorID INT,
        tpep_pickup_datetime TIMESTAMP,
        tpep_dropoff_datetime TIMESTAMP,
        passenger_count INT,
        trip_distance DOUBLE,
        pickup_longitude DOUBLE,
        pickup_latitude DOUBLE,
        RateCodeID INT,
        store_and_fwd_flag STRING,
        dropoff_longitude DOUBLE,
        dropoff_latitude DOUBLE,
        payment_type INT,
        fare_amount DOUBLE,
        extra DOUBLE,
        mta_tax DOUBLE,
        tip_amount DOUBLE,
        tolls_amount DOUBLE,
        improvement_surcharge DOUBLE,
        total_amount DOUBLE,
        pickup_date TIMESTAMP
    )
    USING iceberg
    PARTITIONED BY (pickup_date)
""")

# writing to the new table with the new partition field
df.writeTo("taxi_catalog.db.nyc_taxi_table").using("iceberg").partitionedBy("pickup_date").createOrReplace()
