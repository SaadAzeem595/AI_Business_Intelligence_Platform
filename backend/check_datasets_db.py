import asyncio
from sqlalchemy import select
from app.core.database import AsyncSessionLocal
from app.features.datasets.models import Dataset

async def main():
    async with AsyncSessionLocal() as session:
        stmt = select(Dataset).where(Dataset.project_id == "proj-75cc2d62")
        res = await session.execute(stmt)
        datasets = res.scalars().all()
        print(f"Total datasets in proj-75cc2d62: {len(datasets)}")
        for d in datasets:
            print(f"  ID: {d.id} | Filename: {d.filename} | DuckDB Table: {d.duckdb_table} | Storage: {d.storage_path}")

if __name__ == "__main__":
    asyncio.run(main())
