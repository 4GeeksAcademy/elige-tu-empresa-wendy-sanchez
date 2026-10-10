from sqlalchemy import inspect, text


def migrate_inventory(engine) -> None:
    additions = {
        "medical_supplies": {"expiry_date": "DATE"},
        "supply_consumptions": {"department": "VARCHAR(32)"},
    }
    with engine.begin() as connection:
        for table, fields in additions.items():
            existing = {column["name"] for column in inspect(connection).get_columns(table)}
            for column, data_type in fields.items():
                if column not in existing:
                    connection.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {data_type}"))