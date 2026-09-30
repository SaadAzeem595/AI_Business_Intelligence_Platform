import pytest
import pandas as pd
import numpy as np
import duckdb
from app.features.analytics.engine.date_normalizer import DateTimeNormalizer

def test_case_a_european_slash_hour_minute():
    # A. "13/09/2017 8:59" -> DD/MM/YYYY H:MM
    sample = ["13/09/2017 8:59", "14/09/2017 10:12", "15/09/2017 16:44"]
    result = DateTimeNormalizer.detect_format(sample)
    assert result["detected_type"] in ("datetime", "date")
    assert result["duckdb_format"] == "%d/%m/%Y %H:%M"
    assert result["is_ambiguous"] is False
    assert result["parse_success_rate"] == 1.0

    # Test duckdb SQL expression execution
    con = duckdb.connect()
    con.execute("CREATE TABLE test_a (val VARCHAR)")
    con.execute("INSERT INTO test_a VALUES ('13/09/2017 8:59'), ('14/09/2017 10:12')")
    sql_expr = DateTimeNormalizer.get_duckdb_date_expression("val", result["duckdb_format"])
    res = con.execute(f"SELECT date_trunc('month', {sql_expr}) as m, {sql_expr} as ts FROM test_a").fetchall()
    assert len(res) == 2
    assert res[0][0].month == 9
    assert res[0][0].year == 2017
    assert res[0][1].day == 13
    assert res[0][1].hour == 8
    assert res[0][1].minute == 59

def test_case_b_european_slash_seconds():
    # B. "13/09/2017 08:59:00" -> DD/MM/YYYY HH:MM:SS
    sample = ["13/09/2017 08:59:00", "14/09/2017 10:12:00"]
    result = DateTimeNormalizer.detect_format(sample)
    assert result["duckdb_format"] == "%d/%m/%Y %H:%M:%S"
    assert result["is_ambiguous"] is False
    assert result["parse_success_rate"] == 1.0

def test_case_c_iso_datetime():
    # C. "2017-09-13 08:59:00" -> YYYY-MM-DD HH:MM:SS
    sample = ["2017-09-13 08:59:00", "2017-09-14 10:12:30"]
    result = DateTimeNormalizer.detect_format(sample)
    assert result["duckdb_format"] == "%Y-%m-%d %H:%M:%S"
    assert result["is_ambiguous"] is False
    assert result["parse_success_rate"] == 1.0

def test_case_d_iso_date():
    # D. "2017-09-13" -> YYYY-MM-DD
    sample = ["2017-09-13", "2017-09-14"]
    result = DateTimeNormalizer.detect_format(sample)
    assert result["duckdb_format"] == "%Y-%m-%d"
    assert result["is_ambiguous"] is False
    assert result["parse_success_rate"] == 1.0

def test_case_e_us_12hr_ampm():
    # E. "09/13/2017 8:59 PM" -> MM/DD/YYYY h:MM AM/PM
    sample = ["09/13/2017 8:59 PM", "09/14/2017 10:12 AM"]
    result = DateTimeNormalizer.detect_format(sample)
    assert "%I:%M %p" in result["duckdb_format"] or "%m/%d/%Y" in result["duckdb_format"]
    assert result["is_ambiguous"] is False
    assert result["parse_success_rate"] == 1.0

def test_case_f_year_slash():
    # F. "2017/09/13 08:59" -> YYYY/MM/DD HH:MM
    sample = ["2017/09/13 08:59", "2017/09/14 10:12"]
    result = DateTimeNormalizer.detect_format(sample)
    assert "%Y/%m/%d" in result["duckdb_format"]
    assert result["parse_success_rate"] == 1.0

def test_case_g_h_i_nulls_empties_invalids():
    # G, H, I: NULL values, empty strings, invalid date strings
    sample = [None, "", "   ", "N/A", "null", "invalid_date_abc", "13/09/2017 8:59", "14/09/2017 10:12"]
    result = DateTimeNormalizer.detect_format(sample)
    assert result["detected_type"] in ("datetime", "date")
    assert result["valid_count"] == 2
    assert result["invalid_count"] == 1  # "invalid_date_abc"
    # DuckDB safe parsing should not raise SQL exceptions on invalid strings
    con = duckdb.connect()
    con.execute("CREATE TABLE test_invalids (val VARCHAR)")
    con.execute("INSERT INTO test_invalids VALUES ('13/09/2017 8:59'), ('invalid_abc'), (''), (NULL)")
    sql_expr = DateTimeNormalizer.get_duckdb_date_expression("val", result["duckdb_format"])
    rows = con.execute(f"SELECT val, {sql_expr} as parsed FROM test_invalids").fetchall()
    assert rows[0][1] is not None
    assert rows[1][1] is None
    assert rows[2][1] is None
    assert rows[3][1] is None

def test_case_j_mixed_compatible_formats():
    # J: mixed compatible formats (e.g. ISO date and ISO datetime)
    sample = ["2017-09-13 08:59:00", "2017-09-14", "2017-09-15 10:20"]
    s = pd.Series(sample)
    norm = DateTimeNormalizer.normalize_series(s)
    assert norm.notna().sum() == 3

def test_case_k_ambiguous_date():
    # K: ambiguous "03/04/2018" without values > 12 must be marked ambiguous
    sample = ["03/04/2018", "05/06/2018", "07/08/2018"]
    result = DateTimeNormalizer.detect_format(sample)
    assert result["is_ambiguous"] is True
    assert len(result["candidate_formats"]) >= 2

    # But with a clarifying row > 12: "13/04/2018", it must disambiguate to DD/MM/YYYY
    sample_clarified = ["03/04/2018", "13/04/2018"]
    res_clarified = DateTimeNormalizer.detect_format(sample_clarified)
    assert res_clarified["is_ambiguous"] is False
    assert "%d/%m/%Y" in res_clarified["duckdb_format"]

    # And with "04/13/2018", it must disambiguate to MM/DD/YYYY
    sample_us_clarified = ["03/04/2018", "04/13/2018"]
    res_us_clarified = DateTimeNormalizer.detect_format(sample_us_clarified)
    assert res_us_clarified["is_ambiguous"] is False
    assert "%m/%d/%Y" in res_us_clarified["duckdb_format"]

def test_case_l_m_unix_epoch():
    # L: Unix seconds
    sample_sec = [1505293140, 1505379540, 1505465940]
    res_sec = DateTimeNormalizer.detect_format(sample_sec)
    assert res_sec["detected_type"] in ("datetime", "date")
    assert res_sec["duckdb_format"] == "UNIX_SECONDS"

    con = duckdb.connect()
    con.execute("CREATE TABLE test_unix (val BIGINT)")
    con.execute("INSERT INTO test_unix VALUES (1505293140)")
    sql_expr = DateTimeNormalizer.get_duckdb_date_expression("val", res_sec["duckdb_format"])
    ts = con.execute(f"SELECT {sql_expr} FROM test_unix").fetchone()[0]
    assert ts.year == 2017
    assert ts.month == 9

    # M: Unix milliseconds
    sample_ms = [1505293140000, 1505379540000]
    res_ms = DateTimeNormalizer.detect_format(sample_ms)
    assert res_ms["duckdb_format"] == "UNIX_MILLIS"

def test_case_n_large_dataset_performance():
    # N: large dataset performance test (100K+ rows)
    # DuckDB vectorized conversion
    con = duckdb.connect()
    con.execute("""
        CREATE TABLE test_perf AS 
        SELECT 
            CASE WHEN i % 10 = 0 THEN '13/09/2017 8:59' 
                 WHEN i % 10 = 1 THEN '14/09/2017 10:12'
                 ELSE '15/09/2017 16:44' END AS order_purchase_timestamp
        FROM generate_series(1, 100000) g(i)
    """)
    sql_expr = DateTimeNormalizer.get_duckdb_date_expression("order_purchase_timestamp", "%d/%m/%Y %H:%M")
    query = f"""
        SELECT 
            DATE_TRUNC('month', {sql_expr}) AS period,
            COUNT(*) AS cnt
        FROM test_perf
        WHERE {sql_expr} IS NOT NULL
        GROUP BY 1
        ORDER BY 1
    """
    res = con.execute(query).fetchall()
    assert len(res) == 1
    assert res[0][1] == 100000
