import duckdb


class DuckDBLogger:
    def __init__(self, db_path):
        self.conn = duckdb.connect(db_path)
        self.create_table()

    def create_table(self):
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS opcua_logs (
                timestamp TIMESTAMP,
                node_id VARCHAR,
                value VARCHAR,
                data_type VARCHAR,
            )
        """
        )

    def log_data(self, node_id, value, data_type, timestamp):
        self.conn.execute(
            """
            INSERT INTO opcua_logs (timestamp, node_id, value, data_type)
            VALUES (?, ?, ?, ?)
        """,
            (timestamp, node_id, str(value), data_type),
        )

    def close(self):
        self.conn.close()

    def data_change_handler(self, node, val, data):
        # Existing code...
        if hasattr(self, "duckdb_logger"):
            self.duckdb_logger.log_data(
                node.nodeid.to_string(), val, data.monitored_item.Value.VariantType
            )
