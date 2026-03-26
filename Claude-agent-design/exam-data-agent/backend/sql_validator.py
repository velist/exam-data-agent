import re
import sqlparse
from sqlparse.sql import IdentifierList, Identifier, Parenthesis
from config import ALLOWED_TABLES

DANGEROUS_FUNCTIONS = {"LOAD_FILE", "SLEEP", "BENCHMARK", "GET_LOCK", "RELEASE_LOCK"}
DANGEROUS_KEYWORDS = {"INTO OUTFILE", "INTO DUMPFILE"}


def _extract_table_names(parsed):
    """从解析后的SQL中提取所有表名"""
    tables = set()
    from_seen = False

    for token in parsed.tokens:
        if token.ttype is sqlparse.tokens.Keyword and token.normalized in ("FROM", "JOIN", "INNER JOIN", "LEFT JOIN", "RIGHT JOIN", "CROSS JOIN"):
            from_seen = True
            continue

        if from_seen:
            if isinstance(token, IdentifierList):
                for identifier in token.get_identifiers():
                    # 检查该identifier是否为子查询
                    has_subquery = any(isinstance(t, Parenthesis) for t in identifier.tokens)
                    if has_subquery:
                        # 如果是子查询，递归提取其中的表
                        for t in identifier.tokens:
                            if isinstance(t, Parenthesis):
                                inner_sql = t.value[1:-1].strip()
                                inner_tables = _extract_tables_from_sql(inner_sql)
                                tables.update(inner_tables)
                    else:
                        # 否则，提取表名
                        name = identifier.get_real_name()
                        schema = identifier.get_parent_name()
                        if schema:
                            tables.add(f"{schema}.{name}")
                        elif name:
                            tables.add(name)
                from_seen = False
            elif isinstance(token, Identifier):
                # 检查该identifier是否为子查询
                has_subquery = any(isinstance(t, Parenthesis) for t in token.tokens)
                if has_subquery:
                    # 如果是子查询，递归提取其中的表
                    for t in token.tokens:
                        if isinstance(t, Parenthesis):
                            inner_sql = t.value[1:-1].strip()
                            inner_tables = _extract_tables_from_sql(inner_sql)
                            tables.update(inner_tables)
                else:
                    # 否则，提取表名
                    name = token.get_real_name()
                    schema = token.get_parent_name()
                    if schema:
                        tables.add(f"{schema}.{name}")
                    elif name:
                        tables.add(name)
                from_seen = False
            elif isinstance(token, Parenthesis):
                inner_sql = token.value[1:-1].strip()
                inner_tables = _extract_tables_from_sql(inner_sql)
                tables.update(inner_tables)
                from_seen = False
            elif token.ttype is not sqlparse.tokens.Whitespace:
                from_seen = False

        if isinstance(token, Parenthesis):
            inner_sql = token.value[1:-1].strip()
            inner_tables = _extract_tables_from_sql(inner_sql)
            tables.update(inner_tables)

    return tables


def _extract_tables_from_sql(sql: str) -> set:
    tables = set()
    for statement in sqlparse.parse(sql):
        tables.update(_extract_table_names(statement))
    return tables


def _check_dangerous_patterns(sql_upper: str) -> bool:
    for func in DANGEROUS_FUNCTIONS:
        if re.search(rf'\b{func}\s*\(', sql_upper):
            return False
    for kw in DANGEROUS_KEYWORDS:
        if kw in sql_upper:
            return False
    return True


def _is_table_allowed(table_name: str) -> bool:
    if table_name in ALLOWED_TABLES:
        return True
    if table_name.startswith("dws."):
        return True
    if "." not in table_name:
        return f"dws.{table_name}" in ALLOWED_TABLES or table_name.startswith("dws_")
    return False


def validate_sql(sql: str) -> bool:
    sql = sql.strip().rstrip(";")
    sql_upper = sql.upper()

    parsed_list = sqlparse.parse(sql)
    if not parsed_list:
        return False
    for statement in parsed_list:
        if statement.get_type() != "SELECT":
            return False

    if not _check_dangerous_patterns(sql_upper):
        return False

    for kw in ["INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "CREATE", "TRUNCATE", "GRANT", "REVOKE"]:
        if re.search(rf'\b{kw}\b', sql_upper):
            return False

    tables = _extract_tables_from_sql(sql)
    for table in tables:
        if not _is_table_allowed(table):
            return False

    return True
