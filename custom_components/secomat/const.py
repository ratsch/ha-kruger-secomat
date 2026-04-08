"""Constants for the Krüger Secomat integration."""

DOMAIN = "secomat"

CONF_CLAIM_TOKEN = "claim_token"
CONF_SERIAL = "serial_number"

API_BASE_URL = "https://seco.krueger.ch:8080/app1/v1/plc"

# Polling interval in seconds
DEFAULT_SCAN_INTERVAL = 30

# Secomat states
SECOMAT_STATES = {
    0: "off",
    1: "standby",
    2: "running",
    3: "drying",
    4: "cooling",
    5: "pause",
    6: "ready",
}

# Operating modes
OPERATING_MODES = {
    0: "off",
    1: "laundry_drying",
    2: "room_drying",
    3: "ventilation",
}

# Commands (from app traffic capture)
CMD_WASH_MANUAL_ON = "PRG_WASH_MANUAL_ON"
CMD_WASH_MANUAL_OFF = "PRG_WASH_MANUAL_OFF"
CMD_WASH_AUTO = "PRG_WASH_AUTO"
CMD_ROOM_ON = "PRG_ROOM_ON"
CMD_ROOM_OFF = "PRG_ROOM_OFF"
CMD_PARAMETER_CHANGE = "PARAMETER_CHANGE"

# Target moisture levels (from app: Very Dry / Dry / Normal / Moist)
TARGET_MOISTURE_LEVELS = {
    0: "very_dry",
    1: "dry",
    2: "normal",
    3: "moist",
}

TARGET_MOISTURE_TO_INT = {v: k for k, v in TARGET_MOISTURE_LEVELS.items()}

# Quiet hours defaults (edit here to change)
QUIET_START_WEEKDAY = (22, 0)   # 22:00
QUIET_END_WEEKDAY = (6, 30)     # 06:30
QUIET_START_WEEKEND = (22, 0)   # 22:00
QUIET_END_WEEKEND = (8, 0)      # 08:00
