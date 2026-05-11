"""
Mushroom Agent configuration — species timelines, environmental guardrails,
flush degradation thresholds.

All temporal values in days. Temperatures in Fahrenheit. Humidity in % RH.
"""

SPECIES_TIMELINES = {
    "blue oyster": {
        "colonization_days": (14, 18),
        "days_to_pin":       (3, 5),
        "days_to_harvest":   (4, 6),
        "target_be_pct":     (80, 110),
        "colonization_temp_f":  (70, 77),
        "fruiting_temp_f":      (55, 70),
        "fruiting_humidity_rh": (85, 95),
    },
    "pearl oyster": {
        "colonization_days": (14, 18),
        "days_to_pin":       (3, 5),
        "days_to_harvest":   (4, 6),
        "target_be_pct":     (70, 140),
        "colonization_temp_f":  (70, 77),
        "fruiting_temp_f":      (65, 75),
        "fruiting_humidity_rh": (85, 95),
    },
    "pink oyster": {
        "colonization_days": (10, 14),
        "days_to_pin":       (2, 4),
        "days_to_harvest":   (3, 5),
        "target_be_pct":     (60, 120),
        "colonization_temp_f":  (75, 85),
        "fruiting_temp_f":      (75, 85),
        "fruiting_humidity_rh": (85, 95),
    },
    "golden oyster": {
        "colonization_days": (10, 16),
        "days_to_pin":       (3, 5),
        "days_to_harvest":   (3, 5),
        "target_be_pct":     (50, 100),
        "colonization_temp_f":  (72, 80),
        "fruiting_temp_f":      (65, 75),
        "fruiting_humidity_rh": (85, 95),
    },
    "lions mane": {
        "colonization_days": (18, 24),
        "days_to_pin":       (5, 7),
        "days_to_harvest":   (5, 7),
        "target_be_pct":     (60, 80),
        "colonization_temp_f":  (65, 75),
        "fruiting_temp_f":      (65, 75),
        "fruiting_humidity_rh": (85, 95),
    },
    "shiitake": {
        "colonization_days": (30, 45),
        "days_to_pin":       (7, 10),
        "days_to_harvest":   (5, 8),
        "target_be_pct":     (50, 70),
        "colonization_temp_f":  (65, 75),
        "fruiting_temp_f":      (55, 75),
        "fruiting_humidity_rh": (80, 90),
    },
    "king oyster": {
        "colonization_days": (20, 28),
        "days_to_pin":       (5, 8),
        "days_to_harvest":   (6, 9),
        "target_be_pct":     (70, 90),
        "colonization_temp_f":  (65, 75),
        "fruiting_temp_f":      (55, 65),
        "fruiting_humidity_rh": (85, 95),
    },
    "chestnut": {
        "colonization_days": (18, 25),
        "days_to_pin":       (5, 8),
        "days_to_harvest":   (5, 7),
        "target_be_pct":     (50, 100),
        "colonization_temp_f":  (65, 75),
        "fruiting_temp_f":      (55, 65),
        "fruiting_humidity_rh": (85, 95),
    },
    "reishi": {
        "colonization_days": (25, 40),
        "days_to_pin":       (10, 20),
        "days_to_harvest":   (20, 40),
        "target_be_pct":     (10, 40),
        "colonization_temp_f":  (75, 85),
        "fruiting_temp_f":      (75, 85),
        "fruiting_humidity_rh": (85, 95),
    },
    "maitake": {
        "colonization_days": (30, 50),
        "days_to_pin":       (10, 20),
        "days_to_harvest":   (7, 14),
        "target_be_pct":     (30, 70),
        "colonization_temp_f":  (65, 72),
        "fruiting_temp_f":      (55, 65),
        "fruiting_humidity_rh": (85, 95),
    },
    "nameko": {
        "colonization_days": (20, 30),
        "days_to_pin":       (7, 12),
        "days_to_harvest":   (5, 8),
        "target_be_pct":     (40, 80),
        "colonization_temp_f":  (65, 72),
        "fruiting_temp_f":      (55, 65),
        "fruiting_humidity_rh": (85, 95),
    },
    "pioppino": {
        "colonization_days": (20, 35),
        "days_to_pin":       (7, 14),
        "days_to_harvest":   (5, 10),
        "target_be_pct":     (30, 70),
        "colonization_temp_f":  (65, 75),
        "fruiting_temp_f":      (55, 65),
        "fruiting_humidity_rh": (85, 95),
    },
}

DEFAULT_TIMELINE = {
    "colonization_days": (14, 21),
    "days_to_pin":       (3, 7),
    "days_to_harvest":   (4, 8),
    "target_be_pct":     (50, 100),
    "colonization_temp_f":  (65, 77),
    "fruiting_temp_f":      (65, 75),
    "fruiting_humidity_rh": (85, 95),
}

ENV_GUARDRAILS = {
    "colonizing": {
        "temp_f":       (65, 77),
        "humidity_rh":  (70, 90),
        "consecutive_hours_to_flag": 2,
    },
    "colonized": {
        "temp_f":       (65, 77),
        "humidity_rh":  (70, 90),
        "consecutive_hours_to_flag": 2,
    },
    "pinning": {
        "temp_f":       (65, 72),
        "humidity_rh":  (90, 95),
        "co2_ppm":      (400, 1200),
        "consecutive_hours_to_flag": 2,
    },
    "fruiting": {
        "temp_f":       (65, 72),
        "humidity_rh":  (90, 95),
        "co2_ppm":      (400, 1200),
        "consecutive_hours_to_flag": 2,
    },
    "resting": {
        "temp_f":       (60, 75),
        "humidity_rh":  (80, 92),
        "consecutive_hours_to_flag": 2,
    },
}

FLUSH_DEGRADATION = {
    "normal_max_drop_pct":  50,
    "warning_max_drop_pct": 65,
}

# Minimum completed batches per species before using grower's own historical
# averages instead of species targets
MIN_HISTORY_BATCHES = 5
