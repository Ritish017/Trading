"""
Signal Intelligence Engine — Confidence Calibration Engine
===========================================================
Audits and calibrates signal confidence scores against empirical forward outcomes.

Strict Requirement:
Never treat "confidence = 87%" as a proven probability unless empirically calibrated.
Separates:
- OPPORTUNITY SCORE (Heuristic rule-confluence score, 0-100)
- CONFIDENCE (Heuristic conviction metric, 0-100)
- CALIBRATED PROBABILITY (Observed empirical win rate for that bucket)

Standard Confidence Buckets:
- [50, 60): Midpoint 0.55
- [60, 70): Midpoint 0.65
- [70, 80): Midpoint 0.75
- [80, 90): Midpoint 0.85
- [90, 100]: Midpoint 0.95

A confidence level can ONLY be designated as "CALIBRATED_PROBABILITY" if:
1. The total sample size N >= 100 across evaluated signals.
2. Every bucket has at least 20 observations.
3. The mean calibration error <= 0.10 (10%).
Otherwise, it is strictly stamped as "HEURISTIC_CONFIDENCE".
"""
import logging
from typing import Any, Dict, List, Optional, Tuple
from pydantic import BaseModel, ConfigDict

logger = logging.getLogger(__name__)

MIN_CALIBRATION_TOTAL_SAMPLE = 100
MIN_BUCKET_SAMPLE = 20
MAX_CALIBRATION_ERROR = 0.10


class CalibrationBucket(BaseModel):
    """Evaluation of a single confidence bucket."""
    bucket_name: str
    range_min: float
    range_max: float
    predicted_midpoint: float
    sample_size: int = 0
    actual_wins: int = 0
    actual_win_rate: float = 0.0
    calibration_error: float = 0.0
    brier_score: float = 0.0
    is_calibrated: bool = False
    warning: Optional[str] = None

    model_config = ConfigDict(use_enum_values=True)


class CalibrationReport(BaseModel):
    """Complete calibration audit report."""
    total_sample_size: int = 0
    overall_brier_score: float = 0.0
    mean_calibration_error: float = 0.0
    status: str = "HEURISTIC_CONFIDENCE"  # "HEURISTIC_CONFIDENCE" or "CALIBRATED_PROBABILITY"
    is_calibrated_probability: bool = False
    disclaimer: str
    buckets: List[CalibrationBucket]

    model_config = ConfigDict(use_enum_values=True)


class CalibrationEngine:
    """
    Evaluates observed outcomes against model confidence estimates.
    """

    BUCKET_SPECS = [
        ("50-60", 50.0, 60.0, 0.55),
        ("60-70", 60.0, 70.0, 0.65),
        ("70-80", 70.0, 80.0, 0.75),
        ("80-90", 80.0, 90.0, 0.85),
        ("90-100", 90.0, 100.0, 0.95),
    ]

    @classmethod
    def evaluate_calibration(
        cls,
        confidence_outcome_pairs: List[Tuple[float, bool]],
    ) -> CalibrationReport:
        """
        Evaluate a series of (confidence_score, is_win) pairs.

        Args:
            confidence_outcome_pairs: List of tuples where:
                - confidence_score is float in range 0.0 to 100.0
                - is_win is boolean (True for win, False for loss)

        Returns:
            CalibrationReport with bucket metrics and probability audit status.
        """
        n_total = len(confidence_outcome_pairs)

        # Initialize buckets
        bucket_data = {
            name: {
                "range_min": r_min,
                "range_max": r_max,
                "midpoint": mid,
                "pairs": [],
            }
            for name, r_min, r_max, mid in cls.BUCKET_SPECS
        }

        # Sort pairs into buckets
        for conf, is_win in confidence_outcome_pairs:
            placed = False
            for name, r_min, r_max, mid in cls.BUCKET_SPECS:
                if (r_min <= conf < r_max) or (name == "90-100" and conf == 100.0):
                    bucket_data[name]["pairs"].append((conf / 100.0, 1.0 if is_win else 0.0))
                    placed = True
                    break
            if not placed and conf < 50.0:
                # Group sub-50 into 50-60 for tracking
                bucket_data["50-60"]["pairs"].append((conf / 100.0, 1.0 if is_win else 0.0))

        # Compute bucket stats
        evaluated_buckets: List[CalibrationBucket] = []
        total_sq_error = 0.0
        total_cal_error = 0.0
        valid_buckets_count = 0

        for name, data in bucket_data.items():
            pairs = data["pairs"]
            b_sample = len(pairs)
            midpoint = data["midpoint"]

            if b_sample == 0:
                evaluated_buckets.append(
                    CalibrationBucket(
                        bucket_name=name,
                        range_min=data["range_min"],
                        range_max=data["range_max"],
                        predicted_midpoint=midpoint,
                        sample_size=0,
                        actual_wins=0,
                        actual_win_rate=0.0,
                        calibration_error=0.0,
                        brier_score=0.0,
                        is_calibrated=False,
                        warning="Zero observations in bucket.",
                    )
                )
                continue

            wins = sum(int(target) for _, target in pairs)
            win_rate = wins / b_sample
            cal_error = abs(win_rate - midpoint)

            # Brier score for this bucket: mean((pred - actual)^2)
            brier_sum = sum((pred - target) ** 2 for pred, target in pairs)
            brier_bucket = brier_sum / b_sample

            total_sq_error += brier_sum
            total_cal_error += cal_error
            valid_buckets_count += 1

            is_bucket_calibrated = (
                b_sample >= MIN_BUCKET_SAMPLE and cal_error <= MAX_CALIBRATION_ERROR
            )
            warning = None
            if b_sample < MIN_BUCKET_SAMPLE:
                warning = f"Under-sampled bucket (N={b_sample} < {MIN_BUCKET_SAMPLE}). Not calibrated."
            elif cal_error > MAX_CALIBRATION_ERROR:
                warning = f"High calibration gap ({cal_error:.1%} > {MAX_CALIBRATION_ERROR:.1%}). Heuristic only."

            evaluated_buckets.append(
                CalibrationBucket(
                    bucket_name=name,
                    range_min=data["range_min"],
                    range_max=data["range_max"],
                    predicted_midpoint=midpoint,
                    sample_size=b_sample,
                    actual_wins=wins,
                    actual_win_rate=round(win_rate, 4),
                    calibration_error=round(cal_error, 4),
                    brier_score=round(brier_bucket, 4),
                    is_calibrated=is_bucket_calibrated,
                    warning=warning,
                )
            )

        overall_brier = (total_sq_error / n_total) if n_total > 0 else 0.0
        mean_cal_error = (total_cal_error / valid_buckets_count) if valid_buckets_count > 0 else 0.0

        # Global calibration qualification
        is_global_calibrated = (
            n_total >= MIN_CALIBRATION_TOTAL_SAMPLE
            and all(b.is_calibrated for b in evaluated_buckets if b.sample_size > 0)
            and mean_cal_error <= MAX_CALIBRATION_ERROR
        )

        status = "CALIBRATED_PROBABILITY" if is_global_calibrated else "HEURISTIC_CONFIDENCE"
        if is_global_calibrated:
            disclaimer = (
                f"EMPIRICALLY CALIBRATED: Based on N={n_total} outcomes. "
                f"Mean calibration gap is {mean_cal_error:.1%}. Brier score: {overall_brier:.3f}."
            )
        else:
            disclaimer = (
                f"HEURISTIC ONLY: Confidence scores represent algorithmic conviction weights, "
                f"NOT mathematical probabilities. Total sample size N={n_total} "
                f"(requires N >= {MIN_CALIBRATION_TOTAL_SAMPLE} for empirical calibration)."
            )

        return CalibrationReport(
            total_sample_size=n_total,
            overall_brier_score=round(overall_brier, 4),
            mean_calibration_error=round(mean_cal_error, 4),
            status=status,
            is_calibrated_probability=is_global_calibrated,
            disclaimer=disclaimer,
            buckets=evaluated_buckets,
        )


calibration_engine = CalibrationEngine()
