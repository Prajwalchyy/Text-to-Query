from F00_imports import *


class DatabaseEngine:
    def __init__(self, uri: str = None):
        raw_uri = uri or os.getenv("DATABASE_URL")

        # Resolve relative SQLite URI against backend PROJECT_ROOT if needed
        if raw_uri and raw_uri.startswith("sqlite:///") and not raw_uri.startswith("sqlite:////"):
            rel_db_path = raw_uri.replace("sqlite:///", "")
            abs_db_path = (PROJECT_ROOT / rel_db_path).resolve()
            if abs_db_path.exists():
                self.uri = f"sqlite:///{abs_db_path}"
            else:
                self.uri = raw_uri
        else:
            self.uri = raw_uri

        self.engine = db.create_engine(self.uri)

    def get_table_names(self):
        inspector = db.inspect(self.engine)
        table_list = inspector.get_table_names()
        return table_list

    def get_table_schema(self, table_name: str):
        inspector = db.inspect(self.engine)
        columns_list = inspector.get_columns(table_name)
        return columns_list

    def execute_query(self, sql_query: str):
        with self.engine.connect() as conn:
            result = conn.execute(db.text(sql_query))
            datas = []
            for row in result.mappings():
                datas.append(dict(row))
            return datas


if __name__ == "__main__":
    db_engine = DatabaseEngine()

    print("--- 1. Testing Tables ---")
    tables = db_engine.get_table_names()
    print("Found tables:", tables)

    print("\n--- 2. Testing Schema for 'Artist' ---")
    schema = db_engine.get_table_schema("Artist")
    print("Artist columns:", schema)

    print("\n--- 3. Testing Query Execution ---")
    rows = db_engine.execute_query("SELECT * FROM Artist LIMIT 3;")
    print("Query result:", rows)
