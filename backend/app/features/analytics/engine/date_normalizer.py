"""
Production-Grade Dynamic DateTime Normalization Service for DataPilot AI.
Provides dynamic format detection, disambiguation, safe DuckDB SQL expression generation,
and vectorized Pandas normalization across arbitrary uploaded datasets.
"""

import re
import logging
from typing import Dict, Any, List, Optional, Tuple, Union
from datetime import datetime, timezone
import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)

# Cache for detected date formats: key -> DateDetectionResult dict
_DETECTION_CACHE: Dict[str, Dict[str, Any]] = {}

NULL_REPRESENTATIONS = {
    "", "null", "none", "nan", "nat", "n/a", "na", "undefined", "unknown", "nil", "\\n", "-"
}

# Regex to safely check whether a format string contains only valid strftime specifiers and standard date punctuation
SAFE_STRFTIME_REGEX = re.compile(r'^(?:%[a-zA-Z%]|[-/.:, TtZz+0-9_\s])+$')

# Candidate formats registry: (Display Name, Python strptime, DuckDB strptime, regex pattern, priority)
# Priority: higher numbers tested first
FORMAT_DEFINITIONS: List[Dict[str, Any]] = [
    # --- ISO 8601 & Standards ---
    {
        "name": "YYYY-MM-DD HH:MM:SS",
        "py_fmt": "%Y-%m-%d %H:%M:%S",
        "duck_fmt": "%Y-%m-%d %H:%M:%S",
        "regex": re.compile(r'^\d{4}-\d{2}-\d{2}\s\d{1,2}:\d{2}:\d{2}$'),
        "category": "iso",
        "priority": 100
    },
    {
        "name": "YYYY-MM-DD HH:MM:SS.US",
        "py_fmt": "%Y-%m-%d %H:%M:%S.%f",
        "duck_fmt": "%Y-%m-%d %H:%M:%S.%f",
        "regex": re.compile(r'^\d{4}-\d{2}-\d{2}\s\d{1,2}:\d{2}:\d{2}\.\d+$'),
        "category": "iso",
        "priority": 99
    },
    {
        "name": "YYYY-MM-DDTHH:MM:SS",
        "py_fmt": "%Y-%m-%dT%H:%M:%S",
        "duck_fmt": "%Y-%m-%dT%H:%M:%S",
        "regex": re.compile(r'^\d{4}-\d{2}-\d{2}T\d{1,2}:\d{2}:\d{2}$'),
        "category": "iso",
        "priority": 98
    },
    {
        "name": "YYYY-MM-DDTHH:MM:SSZ",
        "py_fmt": "%Y-%m-%dT%H:%M:%SZ",
        "duck_fmt": "%Y-%m-%dT%H:%M:%SZ",
        "regex": re.compile(r'^\d{4}-\d{2}-\d{2}T\d{1,2}:\d{2}:\d{2}Z$', re.IGNORECASE),
        "category": "iso",
        "priority": 97
    },
    {
        "name": "YYYY-MM-DDTHH:MM:SS.USZ",
        "py_fmt": "%Y-%m-%dT%H:%M:%S.%fZ",
        "duck_fmt": "%Y-%m-%dT%H:%M:%S.%fZ",
        "regex": re.compile(r'^\d{4}-\d{2}-\d{2}T\d{1,2}:\d{2}:\d{2}\.\d+Z$', re.IGNORECASE),
        "category": "iso",
        "priority": 96
    },
    {
        "name": "YYYY-MM-DD HH:MM",
        "py_fmt": "%Y-%m-%d %H:%M",
        "duck_fmt": "%Y-%m-%d %H:%M",
        "regex": re.compile(r'^\d{4}-\d{2}-\d{2}\s\d{1,2}:\d{2}$'),
        "category": "iso",
        "priority": 95
    },
    {
        "name": "YYYY-MM-DD",
        "py_fmt": "%Y-%m-%d",
        "duck_fmt": "%Y-%m-%d",
        "regex": re.compile(r'^\d{4}-\d{2}-\d{2}$'),
        "category": "iso",
        "priority": 90
    },

    # --- European Formats (Day First) ---
    {
        "name": "DD/MM/YYYY HH:MM:SS",
        "py_fmt": "%d/%m/%Y %H:%M:%S",
        "duck_fmt": "%d/%m/%Y %H:%M:%S",
        "regex": re.compile(r'^\d{1,2}/\d{1,2}/\d{4}\s\d{1,2}:\d{2}:\d{2}$'),
        "category": "european",
        "priority": 85
    },
    {
        "name": "DD/MM/YYYY H:MM",
        "py_fmt": "%d/%m/%Y %H:%M",
        "duck_fmt": "%d/%m/%Y %H:%M",
        "regex": re.compile(r'^\d{1,2}/\d{1,2}/\d{4}\s\d{1,2}:\d{2}$'),
        "category": "european",
        "priority": 84
    },
    {
        "name": "DD/MM/YYYY",
        "py_fmt": "%d/%m/%Y",
        "duck_fmt": "%d/%m/%Y",
        "regex": re.compile(r'^\d{1,2}/\d{1,2}/\d{4}$'),
        "category": "european",
        "priority": 80
    },
    {
        "name": "DD-MM-YYYY HH:MM:SS",
        "py_fmt": "%d-%m-%Y %H:%M:%S",
        "duck_fmt": "%d-%m-%Y %H:%M:%S",
        "regex": re.compile(r'^\d{1,2}-\d{1,2}-\d{4}\s\d{1,2}:\d{2}:\d{2}$'),
        "category": "european",
        "priority": 78
    },
    {
        "name": "DD-MM-YYYY HH:MM",
        "py_fmt": "%d-%m-%Y %H:%M",
        "duck_fmt": "%d-%m-%Y %H:%M",
        "regex": re.compile(r'^\d{1,2}-\d{1,2}-\d{4}\s\d{1,2}:\d{2}$'),
        "category": "european",
        "priority": 77
    },
    {
        "name": "DD-MM-YYYY",
        "py_fmt": "%d-%m-%Y",
        "duck_fmt": "%d-%m-%Y",
        "regex": re.compile(r'^\d{1,2}-\d{1,2}-\d{4}$'),
        "category": "european",
        "priority": 76
    },
    {
        "name": "DD.MM.YYYY HH:MM:SS",
        "py_fmt": "%d.%m.%Y %H:%M:%S",
        "duck_fmt": "%d.%m.%Y %H:%M:%S",
        "regex": re.compile(r'^\d{1,2}\.\d{1,2}\.\d{4}\s\d{1,2}:\d{2}:\d{2}$'),
        "category": "european",
        "priority": 75
    },
    {
        "name": "DD.MM.YYYY HH:MM",
        "py_fmt": "%d.%m.%Y %H:%M",
        "duck_fmt": "%d.%m.%Y %H:%M",
        "regex": re.compile(r'^\d{1,2}\.\d{1,2}\.\d{4}\s\d{1,2}:\d{2}$'),
        "category": "european",
        "priority": 74
    },
    {
        "name": "DD.MM.YYYY",
        "py_fmt": "%d.%m.%Y",
        "duck_fmt": "%d.%m.%Y",
        "regex": re.compile(r'^\d{1,2}\.\d{1,2}\.\d{4}$'),
        "category": "european",
        "priority": 73
    },
    {
        "name": "DD/MM/YYYY h:MM:SS AM/PM",
        "py_fmt": "%d/%m/%Y %I:%M:%S %p",
        "duck_fmt": "%d/%m/%Y %I:%M:%S %p",
        "regex": re.compile(r'^\d{1,2}/\d{1,2}/\d{4}\s\d{1,2}:\d{2}:\d{2}\s+(?:AM|PM)$', re.IGNORECASE),
        "category": "european",
        "priority": 72
    },
    {
        "name": "DD/MM/YYYY h:MM AM/PM",
        "py_fmt": "%d/%m/%Y %I:%M %p",
        "duck_fmt": "%d/%m/%Y %I:%M %p",
        "regex": re.compile(r'^\d{1,2}/\d{1,2}/\d{4}\s\d{1,2}:\d{2}\s+(?:AM|PM)$', re.IGNORECASE),
        "category": "european",
        "priority": 71
    },

    # --- US Formats (Month First) ---
    {
        "name": "MM/DD/YYYY HH:MM:SS",
        "py_fmt": "%m/%d/%Y %H:%M:%S",
        "duck_fmt": "%m/%d/%Y %H:%M:%S",
        "regex": re.compile(r'^\d{1,2}/\d{1,2}/\d{4}\s\d{1,2}:\d{2}:\d{2}$'),
        "category": "us",
        "priority": 70
    },
    {
        "name": "MM/DD/YYYY H:MM",
        "py_fmt": "%m/%d/%Y %H:%M",
        "duck_fmt": "%m/%d/%Y %H:%M",
        "regex": re.compile(r'^\d{1,2}/\d{1,2}/\d{4}\s\d{1,2}:\d{2}$'),
        "category": "us",
        "priority": 69
    },
    {
        "name": "MM/DD/YYYY",
        "py_fmt": "%m/%d/%Y",
        "duck_fmt": "%m/%d/%Y",
        "regex": re.compile(r'^\d{1,2}/\d{1,2}/\d{4}$'),
        "category": "us",
        "priority": 68
    },
    {
        "name": "MM/DD/YYYY h:MM:SS AM/PM",
        "py_fmt": "%m/%d/%Y %I:%M:%S %p",
        "duck_fmt": "%m/%d/%Y %I:%M:%S %p",
        "regex": re.compile(r'^\d{1,2}/\d{1,2}/\d{4}\s\d{1,2}:\d{2}:\d{2}\s+(?:AM|PM)$', re.IGNORECASE),
        "category": "us",
        "priority": 67
    },
    {
        "name": "MM/DD/YYYY h:MM AM/PM",
        "py_fmt": "%m/%d/%Y %I:%M %p",
        "duck_fmt": "%m/%d/%Y %I:%M %p",
        "regex": re.compile(r'^\d{1,2}/\d{1,2}/\d{4}\s\d{1,2}:\d{2}\s+(?:AM|PM)$', re.IGNORECASE),
        "category": "us",
        "priority": 66
    },

    # --- Slash Year-First (YYYY/MM/DD) ---
    {
        "name": "YYYY/MM/DD HH:MM:SS",
        "py_fmt": "%Y/%m/%d %H:%M:%S",
        "duck_fmt": "%Y/%m/%d %H:%M:%S",
        "regex": re.compile(r'^\d{4}/\d{1,2}/\d{1,2}\s\d{1,2}:\d{2}:\d{2}$'),
        "category": "other",
        "priority": 65
    },
    {
        "name": "YYYY/MM/DD HH:MM",
        "py_fmt": "%Y/%m/%d %H:%M",
        "duck_fmt": "%Y/%m/%d %H:%M",
        "regex": re.compile(r'^\d{4}/\d{1,2}/\d{1,2}\s\d{1,2}:\d{2}$'),
        "category": "other",
        "priority": 64
    },
    {
        "name": "YYYY/MM/DD",
        "py_fmt": "%Y/%m/%d",
        "duck_fmt": "%Y/%m/%d",
        "regex": re.compile(r'^\d{4}/\d{1,2}/\d{1,2}$'),
        "category": "other",
        "priority": 63
    },

    # --- Named Months ---
    {
        "name": "DD Mon YYYY",
        "py_fmt": "%d %b %Y",
        "duck_fmt": "%d %b %Y",
        "regex": re.compile(r'^\d{1,2}\s+[A-Za-z]{3}\s+\d{4}$'),
        "category": "named_month",
        "priority": 60
    },
    {
        "name": "Mon DD YYYY",
        "py_fmt": "%b %d %Y",
        "duck_fmt": "%b %d %Y",
        "regex": re.compile(r'^[A-Za-z]{3}\s+\d{1,2}\s+\d{4}$'),
        "category": "named_month",
        "priority": 59
    },
    {
        "name": "Month DD, YYYY",
        "py_fmt": "%B %d, %Y",
        "duck_fmt": "%B %d, %Y",
        "regex": re.compile(r'^[A-Za-z]+\s+\d{1,2},\s*\d{4}$'),
        "category": "named_month",
        "priority": 58
    },
    {
        "name": "DD-Mon-YYYY",
        "py_fmt": "%d-%b-%Y",
        "duck_fmt": "%d-%b-%Y",
        "regex": re.compile(r'^\d{1,2}-[A-Za-z]{3}-\d{4}$'),
        "category": "named_month",
        "priority": 57
    },
]


class DateTimeNormalizer:
    """
    Production-grade canonical date/time detection and normalization service.
    Handles data-driven format detection, day/month disambiguation, safe DuckDB SQL 
    generation, and resilient Pandas conversions.
    """

    @classmethod
    def clean_sample_values(cls, values: List[Any]) -> List[str]:
        """Cleans and extracts non-null, non-empty string representations."""
        clean = []
        for v in values:
            if v is None:
                continue
            s = str(v).strip()
            if s.lower() in NULL_REPRESENTATIONS:
                continue
            clean.append(s)
        return clean

    @classmethod
    def detect_format(
        cls,
        sample_values: Union[List[Any], pd.Series],
        column_name: Optional[str] = None,
        user_format: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Inspects representative sample values and detects date/time format,
        reporting parse success, range, and ambiguity status.
        """
        if isinstance(sample_values, pd.Series):
            raw_list = sample_values.dropna().tolist()
        else:
            raw_list = list(sample_values) if sample_values else []

        total_sampled = len(raw_list)
        clean_samples = cls.clean_sample_values(raw_list)

        if not clean_samples:
            return {
                "source_column": column_name or "date",
                "detected_type": "string",
                "detected_format": None,
                "duckdb_format": None,
                "normalized_column": f"__normalized_{column_name or 'date'}",
                "parse_success_rate": 0.0,
                "valid_count": 0,
                "invalid_count": total_sampled,
                "min_timestamp": None,
                "max_timestamp": None,
                "timezone": None,
                "confidence": 0.0,
                "is_ambiguous": False,
                "candidate_formats": [],
                "warnings": ["No valid non-null date values found in sample."]
            }

        # Check for numeric timestamp candidates (Excel serial or Unix epoch)
        numeric_cand = cls._check_numeric_format(clean_samples, column_name)
        if numeric_cand:
            return numeric_cand

        # Test against candidate format definitions
        candidate_scores: List[Dict[str, Any]] = []
        for fmt in FORMAT_DEFINITIONS:
            matched_dates = []
            for val in clean_samples:
                try:
                    # Quick regex check to avoid slow strptime trial on clearly non-matching strings
                    if not fmt["regex"].match(val):
                        continue
                    dt = datetime.strptime(val, fmt["py_fmt"])
                    # Year sanity check (1900 to 2100)
                    if 1900 <= dt.year <= 2100:
                        matched_dates.append(dt)
                except Exception:
                    continue

            if matched_dates:
                candidate_scores.append({
                    "fmt": fmt,
                    "match_count": len(matched_dates),
                    "match_rate": len(matched_dates) / len(clean_samples),
                    "parsed_dates": matched_dates
                })

        # If user explicitly supplied a format, validate it
        if user_format:
            user_res = cls._validate_user_format(clean_samples, user_format, column_name, total_sampled)
            if user_res:
                return user_res

        if not candidate_scores:
            # Fall back to testing pandas general parsing
            return cls._fallback_general_parse(clean_samples, column_name, total_sampled)

        # Sort candidate scores by match_count desc, then priority desc
        candidate_scores.sort(key=lambda c: (c["match_count"], c["fmt"]["priority"]), reverse=True)
        top_cand = candidate_scores[0]

        # Check for Day / Month ambiguity if format uses slashes or hyphens with 2-digit numbers
        is_ambiguous = False
        disambiguated_fmt = top_cand["fmt"]
        candidate_names = [top_cand["fmt"]["name"]]

        # Disambiguate European vs US date formats (DD/MM vs MM/DD)
        if top_cand["fmt"]["category"] in ["european", "us"]:
            disambiguated_fmt, is_ambiguous, candidate_names = cls._disambiguate_day_month(
                clean_samples, top_cand["fmt"], candidate_scores
            )

        # Re-parse sample with the chosen format to calculate exact metrics
        valid_dates = []
        invalid_count = 0
        for val in clean_samples:
            try:
                dt = datetime.strptime(val, disambiguated_fmt["py_fmt"])
                if 1900 <= dt.year <= 2100:
                    valid_dates.append(dt)
                else:
                    invalid_count += 1
            except Exception:
                invalid_count += 1

        valid_count = len(valid_dates)
        success_rate = round(valid_count / len(clean_samples), 4) if clean_samples else 0.0
        confidence = round(success_rate * (0.95 if not is_ambiguous else 0.80), 2)

        min_ts = min(valid_dates).isoformat() if valid_dates else None
        max_ts = max(valid_dates).isoformat() if valid_dates else None

        warnings = []
        if is_ambiguous:
            warnings.append("Date format is ambiguous between Day/Month and Month/Day across all sampled records.")
        if invalid_count > 0:
            warnings.append(f"{invalid_count} values could not be parsed with detected format '{disambiguated_fmt['name']}'.")

        return {
            "source_column": column_name or "date",
            "detected_type": "datetime",
            "detected_format": disambiguated_fmt["name"],
            "duckdb_format": disambiguated_fmt["duck_fmt"],
            "normalized_column": f"__normalized_{column_name or 'date'}",
            "parse_success_rate": success_rate,
            "valid_count": valid_count,
            "invalid_count": invalid_count,
            "null_count": total_sampled - len(clean_samples),
            "min_timestamp": min_ts,
            "max_timestamp": max_ts,
            "timezone": None,
            "confidence": confidence,
            "is_ambiguous": is_ambiguous,
            "candidate_formats": candidate_names,
            "warnings": warnings
        }

    @classmethod
    def _disambiguate_day_month(
        cls,
        samples: List[str],
        best_fmt: Dict[str, Any],
        candidate_scores: List[Dict[str, Any]]
    ) -> Tuple[Dict[str, Any], bool, List[str]]:
        """
        Examines numeric components across all samples.
        If any first token > 12 -> proves DD/MM.
        If any second token > 12 -> proves MM/DD.
        If all first and second tokens <= 12 -> remains ambiguous.
        """
        # Extract first two numbers from strings like 13/09/2017 or 09/13/2017
        num_pattern = re.compile(r'^\s*(\d{1,2})[-/.](\d{1,2})[-/.](\d{2,4})')
        proves_day_first = False
        proves_month_first = False

        for s in samples:
            m = num_pattern.match(s)
            if m:
                part1 = int(m.group(1))
                part2 = int(m.group(2))
                if part1 > 12 and part2 <= 12:
                    proves_day_first = True
                elif part2 > 12 and part1 <= 12:
                    proves_month_first = True

        # Check corresponding European and US formats
        has_ampm = "AM/PM" in best_fmt["name"]
        has_time = "HH:MM" in best_fmt["name"] or "H:MM" in best_fmt["name"]
        has_seconds = "SS" in best_fmt["name"]
        has_hyphen = "-" in best_fmt["name"]
        has_dot = "." in best_fmt["name"]
        sep = "-" if has_hyphen else ("." if has_dot else "/")

        if has_ampm:
            if has_seconds:
                eu_name = f"DD{sep}MM{sep}YYYY h:MM:SS AM/PM"
                us_name = f"MM{sep}DD{sep}YYYY h:MM:SS AM/PM"
            else:
                eu_name = f"DD{sep}MM{sep}YYYY h:MM AM/PM"
                us_name = f"MM{sep}DD{sep}YYYY h:MM AM/PM"
        elif has_time and has_seconds:
            eu_name = f"DD{sep}MM{sep}YYYY HH:MM:SS"
            us_name = f"MM{sep}DD{sep}YYYY HH:MM:SS"
        elif has_time:
            eu_name = f"DD{sep}MM{sep}YYYY H:MM"
            us_name = f"MM{sep}DD{sep}YYYY H:MM"
        else:
            eu_name = f"DD{sep}MM{sep}YYYY"
            us_name = f"MM{sep}DD{sep}YYYY"

        eu_fmt = next((f for f in FORMAT_DEFINITIONS if f["name"] == eu_name), best_fmt)
        us_fmt = next((f for f in FORMAT_DEFINITIONS if f["name"] == us_name), best_fmt)

        if proves_day_first and not proves_month_first:
            return eu_fmt, False, [eu_name]
        elif proves_month_first and not proves_day_first:
            return us_fmt, False, [us_name]
        elif proves_day_first and proves_month_first:
            # Conflicting mixed format column
            return best_fmt, True, [eu_name, us_name]
        else:
            # All tokens <= 12 (ambiguous!)
            return best_fmt, True, [eu_name, us_name]

    @classmethod
    def _check_numeric_format(cls, samples: List[str], column_name: Optional[str]) -> Optional[Dict[str, Any]]:
        """Detects Unix epoch (seconds, ms, us) or Excel serial numbers in numeric strings."""
        try:
            nums = [float(x) for x in samples if re.match(r'^-?\d+(?:\.\d+)?$', x)]
            if len(nums) / len(samples) < 0.8:
                return None

            total = len(nums)
            # Excel serial dates: typically between 30000 (1982) and 65000 (2077)
            if all(30000 <= n <= 65000 for n in nums):
                dts = [datetime.fromordinal(datetime(1899, 12, 30).toordinal() + int(n)) for n in nums]
                return {
                    "source_column": column_name or "date",
                    "detected_type": "datetime",
                    "detected_format": "Excel Serial Date",
                    "duckdb_format": "EXCEL_SERIAL",
                    "normalized_column": f"__normalized_{column_name or 'date'}",
                    "parse_success_rate": 1.0,
                    "valid_count": total,
                    "invalid_count": 0,
                    "min_timestamp": min(dts).isoformat(),
                    "max_timestamp": max(dts).isoformat(),
                    "timezone": None,
                    "confidence": 0.95,
                    "is_ambiguous": False,
                    "candidate_formats": ["Excel Serial Date"],
                    "warnings": []
                }

            # Unix epoch seconds: 9.46e8 (2000-01-01) to 2.5e9 (2049)
            if all(946684800 <= n <= 2500000000 for n in nums):
                dts = [datetime.fromtimestamp(n, timezone.utc) for n in nums]
                return {
                    "source_column": column_name or "date",
                    "detected_type": "datetime",
                    "detected_format": "Unix Timestamp (Seconds)",
                    "duckdb_format": "UNIX_SECONDS",
                    "normalized_column": f"__normalized_{column_name or 'date'}",
                    "parse_success_rate": 1.0,
                    "valid_count": total,
                    "invalid_count": 0,
                    "min_timestamp": min(dts).isoformat(),
                    "max_timestamp": max(dts).isoformat(),
                    "timezone": "UTC",
                    "confidence": 0.95,
                    "is_ambiguous": False,
                    "candidate_formats": ["Unix Timestamp (Seconds)"],
                    "warnings": []
                }

            # Unix epoch milliseconds: 9.46e11 to 2.5e12
            if all(946684800000 <= n <= 2500000000000 for n in nums):
                dts = [datetime.fromtimestamp(n / 1000.0, timezone.utc) for n in nums]
                return {
                    "source_column": column_name or "date",
                    "detected_type": "datetime",
                    "detected_format": "Unix Timestamp (Milliseconds)",
                    "duckdb_format": "UNIX_MILLIS",
                    "normalized_column": f"__normalized_{column_name or 'date'}",
                    "parse_success_rate": 1.0,
                    "valid_count": total,
                    "invalid_count": 0,
                    "min_timestamp": min(dts).isoformat(),
                    "max_timestamp": max(dts).isoformat(),
                    "timezone": "UTC",
                    "confidence": 0.95,
                    "is_ambiguous": False,
                    "candidate_formats": ["Unix Timestamp (Milliseconds)"],
                    "warnings": []
                }
        except Exception:
            pass
        return None

    @classmethod
    def _validate_user_format(
        cls,
        samples: List[str],
        user_format: str,
        column_name: Optional[str],
        total_sampled: int
    ) -> Optional[Dict[str, Any]]:
        """Validates and applies a user-selected format override."""
        matching_def = next(
            (f for f in FORMAT_DEFINITIONS if f["name"].lower() == user_format.lower() or f["duck_fmt"] == user_format),
            None
        )
        py_fmt = matching_def["py_fmt"] if matching_def else user_format
        duck_fmt = matching_def["duck_fmt"] if matching_def else user_format

        # Security validation on format string
        if not SAFE_STRFTIME_REGEX.match(duck_fmt):
            logger.warning(f"Rejected unsafe user format string: {user_format}")
            return None

        valid_dates = []
        invalid_count = 0
        for val in samples:
            try:
                dt = datetime.strptime(val, py_fmt)
                valid_dates.append(dt)
            except Exception:
                invalid_count += 1

        if valid_dates:
            success_rate = round(len(valid_dates) / len(samples), 4)
            return {
                "source_column": column_name or "date",
                "detected_type": "datetime",
                "detected_format": matching_def["name"] if matching_def else user_format,
                "duckdb_format": duck_fmt,
                "normalized_column": f"__normalized_{column_name or 'date'}",
                "parse_success_rate": success_rate,
                "valid_count": len(valid_dates),
                "invalid_count": invalid_count,
                "null_count": total_sampled - len(samples),
                "min_timestamp": min(valid_dates).isoformat(),
                "max_timestamp": max(valid_dates).isoformat(),
                "timezone": None,
                "confidence": 1.0,
                "is_ambiguous": False,
                "candidate_formats": [user_format],
                "warnings": []
            }
        return None

    @classmethod
    def _fallback_general_parse(
        cls,
        samples: List[str],
        column_name: Optional[str],
        total_sampled: int
    ) -> Dict[str, Any]:
        """Fallback to pandas general datetime parser when specific formats fail."""
        try:
            s_parsed = pd.to_datetime(pd.Series(samples), errors="coerce")
            valid = s_parsed.dropna()
            if len(valid) / len(samples) >= 0.7:
                return {
                    "source_column": column_name or "date",
                    "detected_type": "datetime",
                    "detected_format": "Generic ISO / Auto",
                    "duckdb_format": "%Y-%m-%d %H:%M:%S",
                    "normalized_column": f"__normalized_{column_name or 'date'}",
                    "parse_success_rate": round(len(valid) / len(samples), 4),
                    "valid_count": len(valid),
                    "invalid_count": len(samples) - len(valid),
                    "min_timestamp": valid.min().isoformat(),
                    "max_timestamp": valid.max().isoformat(),
                    "timezone": None,
                    "confidence": 0.75,
                    "is_ambiguous": False,
                    "candidate_formats": ["Generic ISO / Auto"],
                    "warnings": ["Detected using generic timestamp parser."]
                }
        except Exception:
            pass

        return {
            "source_column": column_name or "date",
            "detected_type": "string",
            "detected_format": None,
            "duckdb_format": None,
            "normalized_column": f"__normalized_{column_name or 'date'}",
            "parse_success_rate": 0.0,
            "valid_count": 0,
            "invalid_count": total_sampled,
            "min_timestamp": None,
            "max_timestamp": None,
            "timezone": None,
            "confidence": 0.0,
            "is_ambiguous": False,
            "candidate_formats": [],
            "warnings": ["Could not parse column values into valid timestamps."]
        }

    @classmethod
    def get_duckdb_date_expression(
        cls,
        col_ref: str,
        detected_duckdb_format: Optional[str] = None
    ) -> str:
        """
        Builds a robust, non-throwing COALESCE SQL expression in DuckDB.
        Tries the detected format first, then ISO / timestamp cast,
        then a controlled cascade of common formats, and finally Excel/Unix numeric conversions.
        NEVER throws Conversion Error; invalid values return NULL.
        """
        expressions = []

        # 1. Detected format (if safe and valid)
        if detected_duckdb_format:
            clean_fmt = detected_duckdb_format.strip()
            if clean_fmt == "EXCEL_SERIAL":
                expressions.append(
                    f"TRY_CAST(to_timestamp((TRY_CAST({col_ref} AS DOUBLE) - 25569) * 86400) AS TIMESTAMP)"
                )
            elif clean_fmt == "UNIX_SECONDS":
                expressions.append(f"TRY_CAST(to_timestamp(TRY_CAST({col_ref} AS DOUBLE)) AS TIMESTAMP)")
            elif clean_fmt == "UNIX_MILLIS":
                expressions.append(f"TRY_CAST(to_timestamp(TRY_CAST({col_ref} AS DOUBLE) / 1000.0) AS TIMESTAMP)")
            elif SAFE_STRFTIME_REGEX.match(clean_fmt):
                expressions.append(f"try_strptime(CAST({col_ref} AS VARCHAR), '{clean_fmt}')")

        # 2. Native TRY_CAST (efficient for ISO 8601 strings and already-native TIMESTAMP/DATE columns)
        expressions.append(f"TRY_CAST({col_ref} AS TIMESTAMP)")

        # 3. High-confidence standard formats cascade (includes 13/09/2017 8:59 and variants)
        standard_formats = [
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d %H:%M:%S.%f",
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%dT%H:%M:%S.%fZ",
            "%Y-%m-%d %H:%M",
            "%Y-%m-%d",
            "%d/%m/%Y %H:%M:%S",
            "%d/%m/%Y %H:%M",       # <- Specifically covers DD/MM/YYYY H:MM (e.g. 13/09/2017 8:59)
            "%d/%m/%Y",
            "%m/%d/%Y %H:%M:%S",
            "%m/%d/%Y %H:%M",
            "%m/%d/%Y",
            "%m/%d/%Y %I:%M:%S %p",
            "%m/%d/%Y %I:%M %p",
            "%Y/%m/%d %H:%M:%S",
            "%Y/%m/%d %H:%M",
            "%Y/%m/%d",
            "%d-%m-%Y %H:%M:%S",
            "%d-%m-%Y %H:%M",
            "%d-%m-%Y",
            "%d.%m.%Y %H:%M:%S",
            "%d.%m.%Y %H:%M",
            "%d.%m.%Y",
            "%d %b %Y",
            "%b %d, %Y",
        ]

        for fmt in standard_formats:
            expr = f"try_strptime(CAST({col_ref} AS VARCHAR), '{fmt}')"
            if expr not in expressions:
                expressions.append(expr)

        # 4. Numeric fallback handling (Excel serial dates and Unix epochs)
        numeric_case = (
            f"CASE "
            f"  WHEN TRY_CAST({col_ref} AS DOUBLE) BETWEEN 30000 AND 65000 "
            f"    THEN TRY_CAST(to_timestamp((TRY_CAST({col_ref} AS DOUBLE) - 25569) * 86400) AS TIMESTAMP) "
            f"  WHEN TRY_CAST({col_ref} AS DOUBLE) BETWEEN 946684800 AND 2500000000 "
            f"    THEN TRY_CAST(to_timestamp(TRY_CAST({col_ref} AS DOUBLE)) AS TIMESTAMP) "
            f"  WHEN TRY_CAST({col_ref} AS DOUBLE) BETWEEN 946684800000 AND 2500000000000 "
            f"    THEN TRY_CAST(to_timestamp(TRY_CAST({col_ref} AS DOUBLE) / 1000.0) AS TIMESTAMP) "
            f"  ELSE NULL "
            f"END"
        )
        expressions.append(numeric_case)

        return f"COALESCE({', '.join(expressions)})"

    @classmethod
    def normalize_series(
        cls,
        series: pd.Series,
        user_format: Optional[str] = None,
        column_name: Optional[str] = None
    ) -> pd.Series:
        """
        Vectorized Pandas normalization of a series to datetime64[ns].
        Uses data-driven format detection to parse cleanly, handling mixed and invalid values safely.
        """
        if pd.api.types.is_datetime64_any_dtype(series):
            return series

        # Numeric check (Excel serial or Unix epoch)
        if pd.api.types.is_numeric_dtype(series):
            non_null = series.dropna()
            if len(non_null) > 0:
                if ((non_null >= 30000) & (non_null <= 65000)).all():
                    return pd.to_datetime(series, unit='D', origin='1899-12-30', errors='coerce')
                elif ((non_null >= 9.46e8) & (non_null <= 2.5e9)).all():
                    return pd.to_datetime(series, unit='s', errors='coerce')
                elif ((non_null >= 9.46e11) & (non_null <= 2.5e12)).all():
                    return pd.to_datetime(series, unit='ms', errors='coerce')

        # Detect format from non-null sample
        sample_vals = series.dropna().head(100).tolist()
        detection = cls.detect_format(sample_vals, column_name=column_name, user_format=user_format)

        # If detected DuckDB format maps to standard strptime
        duck_fmt = detection.get("duckdb_format")
        if duck_fmt and duck_fmt not in ["EXCEL_SERIAL", "UNIX_SECONDS", "UNIX_MILLIS"]:
            try:
                res = pd.to_datetime(series, format=duck_fmt, errors="coerce")
                if res.dropna().shape[0] == series.dropna().shape[0] and res.dropna().shape[0] > 0:
                    return res
            except Exception:
                pass

        # Try dayfirst=True if detected as European
        is_dayfirst = detection.get("detected_format", "").startswith("DD")
        try:
            res_mixed = pd.to_datetime(series, errors="coerce", format="mixed", dayfirst=is_dayfirst)
            if res_mixed.dropna().shape[0] > 0:
                if duck_fmt and duck_fmt not in ["EXCEL_SERIAL", "UNIX_SECONDS", "UNIX_MILLIS"]:
                    try:
                        res_fmt = pd.to_datetime(series, format=duck_fmt, errors="coerce")
                        if res_fmt.dropna().shape[0] >= res_mixed.dropna().shape[0]:
                            return res_fmt
                    except Exception:
                        pass
                return res_mixed
        except Exception:
            pass

        try:
            return pd.to_datetime(series, errors="coerce", dayfirst=is_dayfirst)
        except Exception:
            return pd.to_datetime(series, errors="coerce")

    @classmethod
    def get_cached_or_detect(
        cls,
        cache_key: str,
        sample_values: List[Any],
        column_name: Optional[str] = None,
        user_format: Optional[str] = None
    ) -> Dict[str, Any]:
        """Retrieves format detection from in-memory cache or computes and caches it."""
        if not user_format and cache_key in _DETECTION_CACHE:
            return _DETECTION_CACHE[cache_key]

        detection = cls.detect_format(sample_values, column_name=column_name, user_format=user_format)
        if not user_format and detection.get("confidence", 0) > 0.5:
            _DETECTION_CACHE[cache_key] = detection
        return detection

    @classmethod
    def clear_cache(cls, key_prefix: Optional[str] = None):
        """Clears cached date format detections."""
        global _DETECTION_CACHE
        if key_prefix:
            _DETECTION_CACHE = {k: v for k, v in _DETECTION_CACHE.items() if not k.startswith(key_prefix)}
        else:
            _DETECTION_CACHE.clear()
