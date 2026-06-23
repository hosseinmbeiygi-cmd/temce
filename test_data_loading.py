import asyncio
from ml.datasets.builders import DatasetBuilder

async def test_data_loading():
    builder = DatasetBuilder()
    try:
        config = {
            "instrument_ids": ["AAPL", "MSFT"],  # مثال برای نمادها
            "start_date": "2023-01-01",  # تاریخ گسترده‌تر
            "end_date": "2023-01-10",
            "horizon": 5,
            "data_source": "yahoo"  # مشخص کردن منبع داده
        }
        features, targets = await builder.load(config)
        print("Data loaded successfully!")
        print(f"Features shape: {features.data.shape}")
        print(f"Targets shape: {targets.data.shape if hasattr(targets, 'data') else len(targets)}")
    except Exception as e:
        print(f"Error loading data: {e}")

if __name__ == "__main__":
    asyncio.run(test_data_loading())
