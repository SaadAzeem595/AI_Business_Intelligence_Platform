# Sample Datasets Reference

To facilitate testing, demonstration, and developer onboarding, five realistic business datasets are provided in the `sample_data/` directory.

---

## 📂 Available Datasets

### 1. Sales Transaction Ledger (`sample_data/sales_data.csv`)
* **Purpose**: Testing aggregate queries, revenue rollups, and region-based groupings.
* **Fields**:
  * `date` (YYYY-MM-DD): The date of the transaction.
  * `customer_id` (String): Alphanumeric customer key (e.g., `C-104`).
  * `product_category` (String): Product department (`Electronics`, `Apparel`, `Home`, `Office`, `Beauty`).
  * `quantity` (Integer): Count of items sold (1–10).
  * `unit_price` (Decimal): Individual price per item ($10.00–$500.00).
  * `region` (String): Geographic area (`North`, `South`, `East`, `West`).
  * `revenue` (Decimal): Calculated gross sale value (`quantity` * `unit_price`).
  * `cost` (Decimal): Calculated cost of goods sold (COGS).

---

### 2. Customer Retention & Churn Profiles (`sample_data/customer_churn_data.csv`)
* **Purpose**: Training binary classifiers, predicting retention risks, and segmentation.
* **Fields**:
  * `customer_id` (String): Customer identifier (e.g., `C-1000`).
  * `age` (Integer): Customer age (18–70).
  * `tenure_months` (Integer): Subscription lifetime duration.
  * `contract_type` (String): Billing cycle (`Month-to-Month`, `One Year`, `Two Year`).
  * `monthly_charges` (Decimal): Monthly subscription rate.
  * `support_tickets` (Integer): Total filed support tickets (0–10).
  * `churn_flag` (Integer): Target indicator (`0` = Retained, `1` = Churned).
  * `total_charges` (Decimal): Total charges (`tenure_months` * `monthly_charges`).

---

### 3. Product Inventory & Cost ledger (`sample_data/product_inventory_data.csv`)
* **Purpose**: Tracking margins, supplier ratings, and stock alerts.
* **Fields**:
  * `product_id` (String): Unique product key (e.g., `P-100`).
  * `product_name` (String): Model naming details.
  * `category` (String): Category classifier (`Hardware`, `Software`, `Accessory`, `Perishable`).
  * `stock_level` (Integer): Current units on hand.
  * `cost_price` (Decimal): Acquisition cost.
  * `selling_price` (Decimal): Retail list price.
  * `reorder_point` (Integer): Minimum inventory threshold before trigger alert.
  * `supplier_rating` (Decimal): Star rating value (3.0–5.0).

---

## 🚀 Step-by-Step Upload & Querying

To analyze these files in local development:

1. **Upload Dataset**:
   * Navigate to the **Datasets** page on the UI.
   * Drag and drop `sample_data/sales_data.csv`.
   * Click **Upload**. The backend profiles the schema, row counts, and health metrics.

2. **Run SQL Queries**:
   * Go to the **SQL Sandbox** page.
   * Enter the query:
     ```sql
     SELECT region, SUM(revenue) as total_rev 
     FROM sales_data 
     GROUP BY region 
     ORDER BY total_rev DESC
     ```
   * Click **Execute** to view DuckDB execution output.

3. **Train Forecast Model**:
   * Go to the **Forecasting** tab.
   * select `sales_data.csv`, target column `revenue`, select model `arima`, and run.
