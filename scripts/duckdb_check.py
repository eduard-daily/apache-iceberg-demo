import duckdb
print(duckdb.query("SELECT 'DuckDB is ready!'").fetchall())
