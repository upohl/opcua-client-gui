import duckdb


class DuckDBLogger:
    def __init__(self):
        # todo IOException handling if file is already in use.
        self.is_connected = False

    def create_table(self):
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS opcua_logs (
                timestamp TIMESTAMP,
                display_name VARCHAR,
                node_id VARCHAR,
                value VARCHAR,
                data_type VARCHAR,
            )
        """
        )
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS opcua_event_logs (
                timestamp TIMESTAMP,
                event VARCHAR,
            )
        """
        )

    def log_data(self, display_name, node_id, value, data_type, timestamp):
        self.conn.execute(
            """
            INSERT INTO opcua_logs (timestamp, display_name, node_id, value, data_type)
            VALUES (?, ?, ?, ?, ?)
        """,
            (timestamp, display_name, node_id, str(value), data_type),
        )

    def log_event(self, event, timestamp):
        self.conn.execute(
            """
            INSERT INTO opcua_event_logs (timestamp, event)
            VALUES (?, ?)
        """,
            (timestamp, event),
        )

    def close(self):
        self.conn.close()
        self.is_connected = False

    def check_if_open(self):
        return self.is_connected

    def connect(self, path):
        self.conn = duckdb.connect(path)
        self.is_connected = True
        self.create_table()

    def data_change_handler(self, node, val, data):
        # Existing code...
        if hasattr(self, "duckdb_logger"):
            self.duckdb_logger.log_data(
                node.nodeid.to_string(), val, data.monitored_item.Value.VariantType
            )
