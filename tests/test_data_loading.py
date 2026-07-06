import asyncio
from ml.datasets.builders import DatasetBuilder

async def test_data_loading():
    builder = DatasetBuilder()
    try:
        config = {
            "instrument_ids": ["فولاد", "خودرو"],  # نمادهای بورس ایران
            "start_date": "2023-01-01",
            "end_date": "2023-01-10",
            "data_source": "tsetmc",
            "timeout": 30,  # افزایش زمان انتظار
            "horizon": 5
        }
        features, targets = await builder.load(config)
        print("Data loaded successfully!")
        print(f"Features shape: {features.data.shape}")
        print(f"Targets shape: {targets.data.shape if hasattr(targets, 'data') else len(targets)}")
    except Exception as e:
        print(f"Error loading data: {e}")

if __name__ == "__main__":
    import sys
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    asyncio.run(test_data_loading())
