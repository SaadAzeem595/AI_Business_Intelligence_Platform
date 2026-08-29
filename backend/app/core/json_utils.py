import json
import math
import decimal
import uuid
import datetime
from typing import Any

def make_json_serializable(obj: Any) -> Any:
    """
    Recursively converts dates, datetimes, numpy/pandas types, Decimals, UUIDs,
    bytes, NaTs, and NaNs into JSON-serializable Python primitives.
    """
    if obj is None:
        return None

    # Standard Primitives
    if isinstance(obj, (int, str, bool)):
        return obj

    # Bytes / Bytearray
    if isinstance(obj, (bytes, bytearray)):
        try:
            return obj.decode("utf-8", errors="replace")
        except Exception:
            return str(obj)

    # Date and Time types
    if isinstance(obj, (datetime.datetime, datetime.date, datetime.time)):
        return obj.isoformat()

    # UUID
    if isinstance(obj, uuid.UUID):
        return str(obj)

    # Decimal
    if isinstance(obj, decimal.Decimal):
        if obj.is_nan() or obj.is_infinite():
            return None
        return float(obj)

    # Numbers and special float values (NaN, Inf)
    if isinstance(obj, float):
        if math.isnan(obj) or math.isinf(obj):
            return None
        return obj

    # Collections (Lists, Tuples, Dicts, Sets) - must check before pandas.isna
    if isinstance(obj, dict):
        return {str(k): make_json_serializable(v) for k, v in obj.items()}

    if isinstance(obj, (list, tuple, set)):
        return [make_json_serializable(item) for item in obj]

    # Numpy array check - must check before pandas.isna
    try:
        import numpy as np
        if isinstance(obj, np.ndarray):
            return [make_json_serializable(item) for item in obj.tolist()]
        if isinstance(obj, (np.integer, np.int64, np.int32, np.int16, np.int8)):
            return int(obj)
        if isinstance(obj, (np.floating, np.float64, np.float32, np.float16)):
            if np.isnan(obj) or np.isinf(obj):
                return None
            return float(obj)
        if isinstance(obj, (np.bool_, bool)):
            return bool(obj)
        if isinstance(obj, np.datetime64):
            try:
                import pandas as pd
                if pd.isna(obj):
                    return None
                return pd.Timestamp(obj).isoformat()
            except Exception:
                return str(obj)
    except ImportError:
        pass

    # Pandas type checks (scalar)
    try:
        import pandas as pd
        if obj is pd.NaT or type(obj).__name__ == "NaTType":
            return None
        if isinstance(obj, pd.Timestamp):
            if pd.isna(obj):
                return None
            return obj.isoformat()
        if isinstance(obj, pd.Timedelta):
            return str(obj)
        # Safely evaluate pd.isna on scalar objects only
        try:
            if pd.isna(obj):
                return None
        except Exception:
            pass
    except ImportError:
        pass

    # Fallback to string representation if object is not recognized
    try:
        return str(obj)
    except Exception:
        return None


class CustomJSONEncoder(json.JSONEncoder):
    """JSONEncoder subclass that uses make_json_serializable for fallback types."""
    def default(self, o: Any) -> Any:
        try:
            return make_json_serializable(o)
        except Exception:
            return super().default(o)


def safe_json_dumps(obj: Any, **kwargs) -> str:
    """Helper function to dump objects to JSON safely without serializability errors."""
    return json.dumps(make_json_serializable(obj), cls=CustomJSONEncoder, **kwargs)
