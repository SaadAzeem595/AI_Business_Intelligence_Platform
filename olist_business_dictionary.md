Dataset: Olist Brazilian E-Commerce

orders:
- order_id
- customer_id
- order_status
- order_purchase_timestamp
- order_delivered_customer_date
- order_estimated_delivery_date

order_items:
- order_id
- product_id
- seller_id
- price
- freight_value

customers:
- customer_id
- customer_unique_id
- customer_city
- customer_state

products:
- product_id
- product_category_name
- product_weight_g
- product_length_cm
- product_height_cm
- product_width_cm

reviews:
- review_id
- order_id
- review_score
- review_comment_title
- review_comment_message

Business definitions:
Revenue = sum(order_items.price)
Freight Revenue = sum(order_items.freight_value)
Order Count = count(distinct order_id)
Average Order Value = Revenue / Order Count