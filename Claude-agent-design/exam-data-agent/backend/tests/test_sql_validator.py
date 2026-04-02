import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from sql_validator import validate_sql


def test_valid_select():
    assert validate_sql("SELECT * FROM dws.dws_active_user_report_week") is True

def test_valid_select_with_where():
    sql = "SELECT start_dt, reg_users FROM dws.dws_active_user_report_week WHERE end_dt > '2026-01-01'"
    assert validate_sql(sql) is True

def test_reject_delete():
    assert validate_sql("DELETE FROM dws.dws_active_user_report_week") is False

def test_reject_drop():
    assert validate_sql("DROP TABLE dws.dws_active_user_report_week") is False

def test_reject_insert():
    assert validate_sql("INSERT INTO dws.dws_active_user_report_week VALUES (1,2,3)") is False

def test_reject_update():
    assert validate_sql("UPDATE dws.dws_active_user_report_week SET reg_users=0") is False

def test_reject_unknown_table():
    assert validate_sql("SELECT * FROM secret_table") is False

def test_reject_unknown_table_no_schema():
    assert validate_sql("SELECT * FROM users") is False

def test_reject_sleep():
    assert validate_sql("SELECT SLEEP(10)") is False

def test_reject_into_outfile():
    assert validate_sql("SELECT * FROM dws.dws_active_user_report_week INTO OUTFILE '/tmp/a'") is False

def test_reject_load_file():
    assert validate_sql("SELECT LOAD_FILE('/etc/passwd')") is False

def test_reject_bigdata_sales():
    assert validate_sql("SELECT sum(售价) FROM bigdata.v_ws_salesflow_ex WHERE 销售部门名称='APP直充'") is False

def test_reject_bigdata_other():
    assert validate_sql("SELECT * FROM bigdata.some_other_table") is False

def test_allow_dws_salesflow():
    sql = "SELECT * FROM dws.dws_v_salesflow_dateil WHERE 销售日期 >= '2026-01-01'"
    assert validate_sql(sql) is True

def test_allow_subquery():
    sql = "SELECT * FROM (SELECT start_dt, reg_users FROM dws.dws_active_user_report_week) t"
    assert validate_sql(sql) is True

def test_reject_union_bad_table():
    sql = "SELECT * FROM dws.dws_active_user_report_week UNION SELECT * FROM secret_table"
    assert validate_sql(sql) is False
