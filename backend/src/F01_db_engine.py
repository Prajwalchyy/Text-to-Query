from F00_imports import *
from typing import List, Dict, Any, Tuple


class DatabaseEngine:
    def __init__(self, uri: str = None):
        raw_uri = uri or os.getenv("DATABASE_URL")

        # Resolve relative SQLite URI against backend PROJECT_ROOT if needed
        if raw_uri != None and raw_uri.startswith("sqlite:///") and raw_uri.startswith("sqlite:////") == False:
            rel_db_path = raw_uri.replace("sqlite:///", "")
            abs_db_path = (PROJECT_ROOT / rel_db_path).resolve()
            if abs_db_path.exists() == True:
                self.uri = f"sqlite:///{abs_db_path}"
            else:
                self.uri = raw_uri
        else:
            self.uri = raw_uri

        self.engine = db.create_engine(self.uri)

    def get_table_names(self) -> List[str]:
        inspector = db.inspect(self.engine)
        table_list = inspector.get_table_names()
        return table_list

    def get_table_schema(self, table_name: str) -> List[Dict[str, Any]]:
        inspector = db.inspect(self.engine)
        columns_list = inspector.get_columns(table_name)
        return columns_list

    def get_table_details(self, table_name: str) -> Tuple[List[Dict[str, Any]], List[str], List[Dict[str, Any]]]:
        """Returns (columns, primary_keys, foreign_keys) for a given table."""
        inspector = db.inspect(self.engine)
        columns_list = inspector.get_columns(table_name)
        pk_constraint = inspector.get_pk_constraint(table_name)
        pks = pk_constraint.get("constrained_columns", []) if pk_constraint != None else []
        fks = inspector.get_foreign_keys(table_name)
        return columns_list, pks, fks

    def get_all_relationships(self) -> List[Dict[str, str]]:
        """Introspects and returns all foreign key relationships across the database."""
        inspector = db.inspect(self.engine)
        relationships = []
        for table in inspector.get_table_names():
            for fk in inspector.get_foreign_keys(table):
                ref_table = fk.get("referred_table")
                con_cols = fk.get("constrained_columns", [])
                ref_cols = fk.get("referred_columns", [])
                for from_col, to_col in zip(con_cols, ref_cols):
                    relationships.append({
                        "from_table": table,
                        "from_col": from_col,
                        "to_table": ref_table,
                        "to_col": to_col
                    })
        return relationships

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

    print("\n--- 2. Testing Relationships ---")
    rels = db_engine.get_all_relationships()
    print("Found relationships:", len(rels))
    for r in rels[:5]:
        print(f" {r['from_table']}.{r['from_col']} -> {r['to_table']}.{r['to_col']}")
