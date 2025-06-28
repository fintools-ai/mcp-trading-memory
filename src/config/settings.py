# MCP Server settings
MCP_SERVER_NAME = "trading-memory"
MCP_SERVER_VERSION = "0.1.0"

# Redis connection settings
REDIS_HOST = "localhost"
REDIS_PORT = 6379
REDIS_DB = 0
REDIS_PASSWORD = None
REDIS_SSL = False
REDIS_DECODE_RESPONSES = True

# Redis connection pool settings
REDIS_MAX_CONNECTIONS = 20
REDIS_CONNECTION_TIMEOUT = 10
REDIS_SOCKET_TIMEOUT = 5
REDIS_SOCKET_KEEPALIVE = True
REDIS_SOCKET_KEEPALIVE_OPTIONS = {}

# Redis retry settings
REDIS_RETRY_ON_TIMEOUT = True
REDIS_RETRY_ON_ERROR = ["ConnectionError", "TimeoutError"]
REDIS_MAX_RETRIES = 3
REDIS_RETRY_DELAY = 0.1
REDIS_BACKOFF_FACTOR = 2.0

# Redis health check settings
REDIS_HEALTH_CHECK_INTERVAL = 30

# Consistency rule settings - 0DTE focused
TIME_GATE_MINUTES = 3  # Default for 0DTE trading - fast decisions needed

WHIPSAW_MAX_CHANGES_PER_HOUR = 2
WHIPSAW_LOOKBACK_MINUTES = 60
WHIPSAW_CHOPPY_THRESHOLD = 3

INVALIDATION_BUFFER_PERCENT = 0.05

# Price movement thresholds for automatic bias invalidation
PRICE_MOVEMENT_THRESHOLDS = [
    {"percent": 0.05, "severity": "warning", "message": "5% adverse move - consider reducing position"},
    {"percent": 0.10, "severity": "high", "message": "10% adverse move - bias likely invalid"},
    {"percent": 0.20, "severity": "critical", "message": "20% adverse move - stop loss triggered"},
]
MAX_ADVERSE_MOVE_PERCENT = 0.20  # 20% max adverse move before forcing bias change

# Storage TTL settings (in seconds)
TTL_BIAS_DATA = 24 * 3600  # 24 hours
TTL_DECISION_HISTORY = 7 * 24 * 3600  # 7 days
TTL_CHANGE_HISTORY = 3 * 24 * 3600  # 3 days
TTL_POSITION_DATA = 24 * 3600  # 24 hours
TTL_SESSION_DATA = 7 * 24 * 3600  # 7 days
TTL_CONSISTENCY_CACHE = 3600  # 1 hour

# Storage limits
STORAGE_HISTORY_LIMIT = 100
STORAGE_POSITION_LIMIT = 20
STORAGE_DECISION_LIMIT = 500

# Logging settings
LOG_LEVEL = "INFO"
LOG_FORMAT = "json"