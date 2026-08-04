import os
import pandas as pd
import numpy as np

# Create directory
os.makedirs("../sample_data", exist_ok=True)

# Generate Sales Data
np.random.seed(42)
dates = pd.date_range(start="2026-01-01", periods=100, freq='D')
sales = pd.DataFrame({
    "date": dates.repeat(5),
    "customer_id": [f"C-{np.random.randint(100, 999)}" for _ in range(500)],
    "product_category": np.random.choice(["Electronics", "Apparel", "Home", "Office", "Beauty"], 500),
    "quantity": np.random.randint(1, 10, 500),
    "unit_price": np.random.uniform(10.0, 500.0, 500).round(2),
    "region": np.random.choice(["North", "South", "East", "West"], 500)
})
sales["revenue"] = (sales["quantity"] * sales["unit_price"]).round(2)
sales["cost"] = (sales["revenue"] * np.random.uniform(0.4, 0.7, 500)).round(2)
sales.to_csv("../sample_data/sales_data.csv", index=False)

# Generate Customer Churn Data
churn = pd.DataFrame({
    "customer_id": [f"C-{1000 + i}" for i in range(200)],
    "age": np.random.randint(18, 70, 200),
    "tenure_months": np.random.randint(1, 72, 200),
    "contract_type": np.random.choice(["Month-to-Month", "One Year", "Two Year"], 200),
    "monthly_charges": np.random.uniform(20.0, 120.0, 200).round(2),
    "support_tickets": np.random.randint(0, 10, 200),
    "churn_flag": np.random.choice([0, 1], 200, p=[0.75, 0.25])
})
churn["total_charges"] = (churn["tenure_months"] * churn["monthly_charges"]).round(2)
churn.to_csv("../sample_data/customer_churn_data.csv", index=False)

# Generate Product Inventory Data
inventory = pd.DataFrame({
    "product_id": [f"P-{100 + i}" for i in range(100)],
    "product_name": [f"Widget Model {chr(65 + (i % 26))}{i}" for i in range(100)],
    "category": np.random.choice(["Hardware", "Software", "Accessory", "Perishable"], 100),
    "stock_level": np.random.randint(5, 500, 100),
    "cost_price": np.random.uniform(5.0, 200.0, 100).round(2)
})
inventory["selling_price"] = (inventory["cost_price"] * np.random.uniform(1.2, 1.8, 100)).round(2)
inventory["reorder_point"] = np.random.randint(10, 50, 100)
inventory["supplier_rating"] = np.random.uniform(3.0, 5.0, 100).round(1)
inventory.to_csv("../sample_data/product_inventory_data.csv", index=False)

# Generate Financial KPIs
financials = pd.DataFrame({
    "date": pd.date_range(start="2026-01-01", periods=100, freq='D'),
    "revenue": np.random.uniform(500, 1500, 100).round(2),
    "cost": np.random.uniform(300, 900, 100).round(2),
    "marketing_spend": np.random.uniform(50, 200, 100).round(2),
    "conversions": np.random.randint(10, 80, 100),
    "visitors": np.random.randint(200, 1000, 100),
    "region": np.random.choice(["North", "South", "East", "West"], 100)
})
financials["profit"] = (financials["revenue"] - financials["cost"]).round(2)
# Add outlier anomaly
financials.loc[15, "revenue"] = 8500.0
financials.loc[15, "profit"] = 7900.0
financials.to_csv("../sample_data/financial_kpis.csv", index=False)

# Generate Marketing Campaigns
marketing = pd.DataFrame({
    "campaign_id": [f"MKT-{100 + i}" for i in range(50)],
    "start_date": pd.date_range(start="2026-01-01", periods=50, freq='W').strftime("%Y-%m-%d"),
    "channel": np.random.choice(["Google Ads", "Facebook Ads", "Email Newsletters", "LinkedIn Ads", "SEO Organic"], 50),
    "spend": np.random.uniform(100.0, 2000.0, 50).round(2),
    "impressions": np.random.randint(1000, 50000, 50)
})
marketing["clicks"] = (marketing["impressions"] * np.random.uniform(0.01, 0.05, 50)).astype(int)
marketing["conversions"] = (marketing["clicks"] * np.random.uniform(0.02, 0.10, 50)).astype(int)
marketing["revenue_generated"] = (marketing["conversions"] * np.random.uniform(50, 200, 50)).round(2)
marketing.to_csv("../sample_data/marketing_campaigns.csv", index=False)

print("Generated sample CSV files in sample_data/ directory.")
