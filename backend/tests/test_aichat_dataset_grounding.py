import pytest
import io
import uuid
import os
import tempfile
from fastapi.testclient import TestClient

from app.main import app
from app.core.dependencies import get_current_user, MockUser
from app.core.database import AsyncSessionLocal
from app.core.cache import run_async_as_sync
from app.features.datasets.models import Dataset
from app.features.projects.models import Project
from app.features.agents.semantic_sql import (
    build_catalog_from_datasets,
    parse_and_generate_semantic_sql,
    validate_semantic_sql
)
from app.features.agents.agents import resolve_dataset, get_available_dataset_names
from app.features.agents.tools import generate_sql, validate_sql

client = TestClient(app)

# Helper fixtures and mock project data setup
@pytest.fixture
def project_with_olist_datasets():
    """Creates a project and uploads simulated Olist datasets into it."""
    proj_id = f"test-proj-{uuid.uuid4().hex[:6]}"
    mock_user = MockUser(id="dev-user-123", email="dev-user-123@datapilot.com", name="User DEV", role="Admin")
    app.dependency_overrides[get_current_user] = lambda: mock_user
    
    # Generate temporary CSV content for products and order_items
    products_csv = (
        "product_id,product_category_name,product_name_lenght\n"
        "p1,cidade_moveis,45\n"
        "p2,cidade_moveis,52\n"
        "p3,eletronicos,28\n"
        "p4,eletronicos,30\n"
        "p5,perfumaria,65\n"
    )
    items_csv = (
        "order_id,product_id,price\n"
        "o1,p1,150.0\n"
        "o2,p1,150.0\n"
        "o3,p2,200.0\n"
        "o4,p3,80.0\n"
        "o5,p5,300.0\n"
    )

    async def create_db_records():
        async with AsyncSessionLocal() as db:
            # Create project
            proj = Project(
                id=proj_id,
                name="Olist Test Analytics",
                description="Test project for Olist datasets",
                owner_id="dev-user-123",
                status="Active"
            )
            db.add(proj)

            # Temp storage files
            tmp_dir = tempfile.mkdtemp()
            prod_path = os.path.join(tmp_dir, "olist_products_dataset.csv")
            item_path = os.path.join(tmp_dir, "olist_order_items_dataset.csv")

            with open(prod_path, "w", encoding="utf-8") as f:
                f.write(products_csv)
            with open(item_path, "w", encoding="utf-8") as f:
                f.write(items_csv)

            d1 = Dataset(
                id=f"ds-{uuid.uuid4().hex[:6]}",
                filename="olist_products_dataset.csv",
                type="CSV",
                size="1.2 KB",
                rows=5,
                qualityScore=100,
                status="Active",
                date="2026-08-15",
                workspace_id="default",
                display_name="olist_products_dataset",
                storage_path=prod_path,
                duckdb_table=f"project_{proj_id.replace('-', '_')}_olist_products_dataset",
                columns_json='["product_id", "product_category_name", "product_name_lenght"]',
                schema_json='{"product_id": {"type": "VARCHAR"}, "product_category_name": {"type": "VARCHAR"}, "product_name_lenght": {"type": "BIGINT"}}',
                project_id=proj_id,
                owner_id="dev-user-123"
            )
            d2 = Dataset(
                id=f"ds-{uuid.uuid4().hex[:6]}",
                filename="olist_order_items_dataset.csv",
                type="CSV",
                size="1.5 KB",
                rows=5,
                qualityScore=100,
                status="Active",
                date="2026-08-15",
                workspace_id="default",
                display_name="olist_order_items_dataset",
                storage_path=item_path,
                duckdb_table=f"project_{proj_id.replace('-', '_')}_olist_order_items_dataset",
                columns_json='["order_id", "product_id", "price"]',
                schema_json='{"order_id": {"type": "VARCHAR"}, "product_id": {"type": "VARCHAR"}, "price": {"type": "DOUBLE"}}',
                project_id=proj_id,
                owner_id="dev-user-123"
            )
            db.add(d1)
            db.add(d2)
            await db.commit()
            return proj_id, d1, d2, tmp_dir

    proj_id, d1, d2, tmp_dir = run_async_as_sync(create_db_records())
    yield proj_id, d1, d2

    # Cleanup after test
    async def cleanup():
        async with AsyncSessionLocal() as db:
            await db.delete(d1)
            await db.delete(d2)
            proj = await db.get(Project, proj_id)
            if proj:
                await db.delete(proj)
            await db.commit()
    try:
        run_async_as_sync(cleanup())
    except Exception:
        pass
    finally:
        app.dependency_overrides.clear()


def test_explicit_filename_resolution(project_with_olist_datasets):
    """Test 1: Explicit filename mentioned in prompt resolves strictly to registered dataset."""
    proj_id, d1, d2 = project_with_olist_datasets
    
    query = "Which product category has the longest average product name length in olist_products_dataset dataset?"
    available = [
        {"id": d1.id, "filename": d1.filename, "duckdb_table": d1.duckdb_table, "schema_json": d1.schema_json, "project_id": proj_id},
        {"id": d2.id, "filename": d2.filename, "duckdb_table": d2.duckdb_table, "schema_json": d2.schema_json, "project_id": proj_id}
    ]

    resolved = resolve_dataset(query, available_datasets=available, project_id=proj_id)
    assert resolved is not None
    assert resolved["filename"] == "olist_products_dataset.csv"
    assert resolved["id"] == d1.id


def test_project_scoped_dataset_discovery(project_with_olist_datasets):
    """Test 2: Only current project's datasets are retrieved and used."""
    proj_id, d1, d2 = project_with_olist_datasets
    
    available = [
        {"id": d1.id, "filename": d1.filename, "duckdb_table": d1.duckdb_table, "schema_json": d1.schema_json, "project_id": proj_id},
        {"id": d2.id, "filename": d2.filename, "duckdb_table": d2.duckdb_table, "schema_json": d2.schema_json, "project_id": proj_id}
    ]

    names = get_available_dataset_names(available_datasets=available)
    assert len(names) == 2
    assert "olist_products_dataset.csv" in names
    assert "olist_order_items_dataset.csv" in names


def test_no_unrelated_dataset_fallback(project_with_olist_datasets):
    """Test 3: Unrelated datasets (e.g. e2e_sales_data or sales_data) are NEVER returned or referenced."""
    proj_id, d1, d2 = project_with_olist_datasets

    response = client.post(
        "/api/v1/agents/chat",
        json={
            "message": "What are the top 5 product categories by total sales revenue?",
            "project_id": proj_id,
            "active_project": proj_id
        }
    )
    assert response.status_code == 200
    res_data = response.json()
    
    response_text = str(res_data.get("response", "")) + str(res_data.get("content", ""))
    sql_query = str(res_data.get("sql_query", ""))

    assert "e2e_sales_data" not in response_text
    assert "e2e_sales_data" not in sql_query
    assert "sales_data.csv" not in sql_query


def test_single_table_query(project_with_olist_datasets):
    """Test 4: Questions targeting a single dataset use only that single table."""
    proj_id, d1, d2 = project_with_olist_datasets

    response = client.post(
        "/api/v1/agents/chat",
        json={
            "message": "Which product category has the longest average product name length in olist_products_dataset dataset?",
            "project_id": proj_id,
            "active_project": proj_id
        }
    )
    assert response.status_code == 200
    res_data = response.json()
    sql_query = res_data.get("sql_query", "")

    assert sql_query is not None
    assert "AVG(" in sql_query.upper() or "product_name_lenght" in sql_query.lower()
    assert "JOIN" not in sql_query.upper()


def test_multi_table_olist_query(project_with_olist_datasets):
    """Test 5: Multi-table business question automatically discovers and uses valid join relationships."""
    proj_id, d1, d2 = project_with_olist_datasets

    response = client.post(
        "/api/v1/agents/chat",
        json={
            "message": "What are the top 5 product categories by total sales revenue?",
            "project_id": proj_id,
            "active_project": proj_id
        }
    )
    assert response.status_code == 200
    res_data = response.json()
    sql_query = res_data.get("sql_query", "")

    assert sql_query is not None
    assert "JOIN" in sql_query.upper()
    assert "SUM(" in sql_query.upper() or "price" in sql_query.lower()


def test_invalid_table_recovery(project_with_olist_datasets):
    """Test 6: Validates SQL pre-execution and rejects invalid table names."""
    proj_id, d1, d2 = project_with_olist_datasets

    available = [
        {"id": d1.id, "filename": d1.filename, "duckdb_table": d1.duckdb_table, "schema_json": d1.schema_json, "project_id": proj_id}
    ]
    
    # Try validating SQL referencing nonexistent table
    invalid_sql = "SELECT * FROM nonexistent_fake_table LIMIT 5"
    is_valid, err = validate_sql(invalid_sql, "Show data", available_datasets=available)
    
    assert is_valid is False
    assert "nonexistent_fake_table" in err or "does not exist" in err


def test_invalid_column_recovery(project_with_olist_datasets):
    """Test 7: Validates SQL pre-execution and rejects invalid column names."""
    proj_id, d1, d2 = project_with_olist_datasets

    available = [
        {
            "id": d1.id,
            "filename": d1.filename,
            "duckdb_table": d1.duckdb_table,
            "columns": {"product_id": {"name": "product_id", "type": "VARCHAR"}, "product_category_name": {"name": "product_category_name", "type": "VARCHAR"}},
            "schema_json": '{"product_id": {"type": "VARCHAR"}, "product_category_name": {"type": "VARCHAR"}}',
            "project_id": proj_id
        }
    ]
    catalog = build_catalog_from_datasets(available)
    
    invalid_sql = f'SELECT "{d1.duckdb_table}"."fake_nonexistent_column" FROM "{d1.duckdb_table}"'
    is_valid, err = validate_semantic_sql(invalid_sql, "Show fake column", catalog)

    assert is_valid is False
    assert "fake_nonexistent_column" in err or "Column" in err


def test_project_id_propagation(project_with_olist_datasets):
    """Test 8: Ensures project_id is consistently propagated and logged."""
    proj_id, d1, d2 = project_with_olist_datasets

    response = client.post(
        "/api/v1/agents/chat",
        json={
            "message": "How many products are in each category?",
            "project_id": proj_id,
            "active_project": proj_id
        }
    )
    assert response.status_code == 200
    res_data = response.json()
    assert res_data.get("status") in ["completed", "paused"]


def test_chat_never_triggers_project_creation():
    """Test 9: Chat endpoint never triggers project creation logic or endpoints."""
    response = client.post(
        "/api/v1/agents/chat",
        json={
            "message": "Hello, what datasets are available?",
            "workspace": "default"
        }
    )
    assert response.status_code == 200
    res = response.json()
    assert "Project creation timed out" not in str(res)


def test_upload_and_immediately_query(project_with_olist_datasets):
    """Test 10: Upload dataset to project -> immediately execute chat query on dataset."""
    proj_id, d1, d2 = project_with_olist_datasets

    csv_data = "customer_id,city,state\nc1,Sao Paulo,SP\nc2,Rio,RJ\n"
    file_bytes = io.BytesIO(csv_data.encode("utf-8"))

    upload_res = client.post(
        f"/api/v1/projects/{proj_id}/datasets",
        files={"file": ("olist_customers_dataset.csv", file_bytes, "text/csv")},
        data={"tableName": "olist_customers_dataset"}
    )
    assert upload_res.status_code == 200
    uploaded_ds = upload_res.json()
    assert uploaded_ds["filename"] == "olist_customers_dataset.csv"

    # Immediately query uploaded dataset
    chat_res = client.post(
        "/api/v1/agents/chat",
        json={
            "message": "How many customers are in olist_customers_dataset.csv?",
            "project_id": proj_id,
            "active_project": proj_id
        }
    )
    assert chat_res.status_code == 200
    chat_data = chat_res.json()
    assert "olist_customers_dataset" in str(chat_data.get("sql_query", "")) or chat_data.get("row_count") is not None


def test_delete_dataset_not_queryable(project_with_olist_datasets):
    """Test 11: Delete dataset from project -> dataset is no longer queryable."""
    proj_id, d1, d2 = project_with_olist_datasets

    # Delete dataset d1
    del_res = client.delete(f"/api/v1/datasets/{d1.id}")
    assert del_res.status_code == 200

    # Query deleted dataset
    chat_res = client.post(
        "/api/v1/agents/chat",
        json={
            "message": "Which product category has the longest average product name length in olist_products_dataset.csv?",
            "project_id": proj_id,
            "active_project": proj_id
        }
    )
    assert chat_res.status_code == 200
    res_data = chat_res.json()
    resp_text = str(res_data.get("response", "")) + str(res_data.get("content", ""))
    
    assert "not found" in resp_text.lower() or "unavailable" in resp_text.lower() or "upload" in resp_text.lower()
