import duckdb

conn = duckdb.connect()
orders_p = "D:/AI Business Intelligence Platform/backend/app/uploads/0d057378-3ada-4acf-9d15-d0a52d614fdc_olist_orders_dataset.csv"
items_p = "D:/AI Business Intelligence Platform/backend/app/uploads/61341e3a-16a0-4910-9115-9d1bd6eed483_olist_order_items_dataset.csv"
conn.execute(f"CREATE VIEW orders AS SELECT * FROM read_csv_auto('{orders_p}')")
conn.execute(f"CREATE VIEW items AS SELECT * FROM read_csv_auto('{items_p}')")

res = conn.execute("""
    SELECT 
        COUNT(DISTINCT o.order_id) as total_orders,
        ROUND(SUM(i.price), 2) as total_revenue,
        ROUND(SUM(i.freight_value), 2) as total_freight,
        COUNT(DISTINCT o.customer_id) as total_customers,
        ROUND(SUM(i.price) / COUNT(DISTINCT o.order_id), 2) as avg_order_value,
        MIN(o.order_purchase_timestamp) as min_date,
        MAX(o.order_purchase_timestamp) as max_date
    FROM orders o
    JOIN items i ON o.order_id = i.order_id
""").fetchall()

print("OLIST OVERALL METRICS:")
print("Orders:", res[0][0])
print("Revenue:", res[0][1])
print("Freight:", res[0][2])
print("Customers:", res[0][3])
print("AOV:", res[0][4])
print("Min Date:", res[0][5])
print("Max Date:", res[0][6])
