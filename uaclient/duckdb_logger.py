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
                server VARCHAR
            )
        """
        )
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS opcua_event_logs (
                timestamp TIMESTAMP,
                event VARCHAR,
                server VARCHAR
            )
        """
        )

    def log_data(self, display_name, node_id, value, data_type, timestamp, server):
        self.conn.execute(
            """
            INSERT INTO opcua_logs (timestamp, display_name, node_id, value, data_type, server)
            VALUES (?, ?, ?, ?, ?, ?)
        """,
            (timestamp, display_name, node_id, str(value), data_type, server),
        )

    def log_event(self, event, timestamp, server): #TODO: Eventstring in Json umformen und in DuckDB als Json speichern
        self.conn.execute(
            """
            INSERT INTO opcua_event_logs (timestamp, event, server)
            VALUES (?, ?, ?)
        """,
            (timestamp, event, server),
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

    def get_last_10_data(self, path):
        try:
            notConnected = False
            if not self.is_connected:
                self.connect(path)
                notConnected = True
            self.result = self.conn.sql(
                """
                SELECT timestamp, display_name, node_id, value, server FROM opcua_logs ORDER BY timestamp DESC LIMIT 100;
            """
            ).fetchmany(100)
            if notConnected:
                self.close()
            return self.result
        except Exception as e:
            print("Unable to connect to duckdb")
            return None
