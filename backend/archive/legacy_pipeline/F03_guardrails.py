from F00_imports import *
from F01_db_engine import DatabaseEngine


class SQLInjectionGuardrail:
    FORBIDDEN_KEYWORDS = {
        "DROP",
        "DELETE",
        "UPDATE",
        "INSERT",
        "ALTER",
        "TRUNCATE",
        "REPLACE",
        "CREATE",
        "GRANT",
        "REVOKE",
        "EXEC",
        "EXECUTE",
        "SHUTDOWN",
        "ATTACH",
        "DETACH",
    }

    def __init__(self, db_engine: DatabaseEngine = None):
        self.db_engine = db_engine or DatabaseEngine()
        self.allowed_tables: Set[str] = {
            table.lower() for table in self.db_engine.get_table_names()
        }

    def check_keyword_not_allowed(self, sql: str) -> Optional[str]:
        """
        Layer 1: Scans SQL for destructive keywords using regex word boundaries.
        Returns an error message if forbidden word found, otherwise None.
        """
        pattern = r"\b(" + "|".join(self.FORBIDDEN_KEYWORDS) + r")\b"
        match = re.search(pattern, sql, re.IGNORECASE)

        if match:
            forbidden_word = match.group(1).upper()
            return f"Security Violation: Forbidden keyword '{forbidden_word}' detected."

        return None

    def check_ast_and_multi_query(self, sql: str):
        """
        Layer 2 & 3: Parses SQL with sqlglot.
        - Blocks multi-query chained attacks (e.g. SELECT 1; DROP TABLE users;)
        - Verifies root expression is strictly a SELECT statement.
        Returns: (parsed_expression, error_message)
        """
        try:
            parsed_statements = sqlglot.parse(sql, read="sqlite")
        except Exception as e:
            return None, f"SQL Syntax Error: Unable to parse query ({str(e)})"

        # Layer 3: Block multiple / chained queries
        if len(parsed_statements) > 1:
            return None, "Security Violation: Multi-statement / chained queries are forbidden."

        if not parsed_statements or parsed_statements[0] is None:
            return None, "SQL Error: Empty query provided."

        statement = parsed_statements[0]

        # Layer 2: Must be strictly a SELECT or UNION expression
        if not isinstance(statement, (exp.Select, exp.Union)):
            return None, f"Security Violation: Only SELECT/UNION queries are permitted (got {type(statement).__name__})."

        return statement, None

    def check_table_allowlist(self, statement: exp.Expression) -> Optional[str]:
        """
        Layer 4: Extracts all table names from parsed AST and ensures
        they exist in the database schema allowlist.
        Recognizes and permits local CTE (WITH ...) aliases.
        """
        cte_names = {cte.alias.lower() for cte in statement.find_all(exp.CTE) if cte.alias}

        for table_node in statement.find_all(exp.Table):
            table_name = table_node.name.lower()
            if table_name in cte_names:
                continue
            if table_name not in self.allowed_tables:
                return f"Schema Violation: Table '{table_node.name}' does not exist in database allowlist."
        return None

    def validate_sql(self, raw_sql: str):
        """
        Master Pipeline: Runs incoming SQL through all 4 security layers.
        Returns: (is_valid: bool, reason: str, sanitized_sql: str)
        """
        sql = raw_sql.strip()

        # Remove trailing semicolon for clean processing
        if sql.endswith(";"):
            sql = sql[:-1].strip()

        # 1. Layer 1 Check: Keyword Denylist
        keyword_error = self.check_keyword_not_allowed(sql)
        if keyword_error:
            return False, keyword_error, ""

        # 2. Layer 2 & 3 Check: AST & Multi-Query Blocker
        statement, ast_error = self.check_ast_and_multi_query(sql)
        if ast_error:
            return False, ast_error, ""

        # 3. Layer 4 Check: Schema Allowlist
        allowlist_error = self.check_table_allowlist(statement)
        if allowlist_error:
            return False, allowlist_error, ""

        # All 4 layers passed successfully!
        return True, "Passed all security guardrails.", sql + ";"


if __name__ == "__main__":
    guardrail = SQLInjectionGuardrail()

    # Test Suite: Safe queries vs Attack payloads
    test_cases = [
        # Safe queries
        ("SELECT * FROM Artist LIMIT 5;", True),
        ("SELECT c.FirstName, i.Total FROM Customer c JOIN Invoice i ON c.CustomerId = i.CustomerId;", True),

        # Malicious attacks
        ("DROP TABLE Customer;", False),
        ("DELETE FROM Invoice WHERE Total > 10;", False),
        ("SELECT * FROM Track; DROP TABLE Album;", False),
        ("SELECT * FROM passwords_table;", False),
        ("UPDATE Customer SET Email = 'hacked@hack.com';", False),
    ]

    print("--- RUNNING SECURITY GUARDRAIL TEST SUITE ---\n")
    all_passed = True
    for i, (query, expected_safe) in enumerate(test_cases, 1):
        is_valid, reason, sanitized_sql = guardrail.validate_sql(query)
        passed_test = (is_valid == expected_safe)
        status = "[PASS]" if passed_test else "[FAIL]"

        print(f"Test {i}: {status}")
        print(f"  Query:  {query}")
        print(f"  Safe:   {is_valid} (Expected: {expected_safe})")
        print(f"  Reason: {reason}\n")

        if not passed_test:
            all_passed = False

    if all_passed:
        print("[SUCCESS] ALL SECURITY GUARDRAIL TESTS PASSED 100%!")
