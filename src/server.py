"""FastMCP Trading Memory Server implementation without globals."""

import argparse
import asyncio
import logging
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, Optional

# Add the parent directory to the Python path to allow src imports
current_dir = Path(__file__).resolve().parent
parent_dir = current_dir.parent
sys.path.insert(0, str(parent_dir))

from fastmcp import FastMCP

from src.config import settings
from src.storage.memory_store import MemoryStore
from src.tools.check_consistency import CheckConsistencyTool
from src.tools.get_current_bias import GetCurrentBiasTool
from src.tools.store_trading_decision import StoreTradingDecisionTool
from src.tools.force_reset import ForceResetTool


class TradingMemoryServer:
    def __init__(self) -> None:
        # Setup simple logging
        logging.basicConfig(
            level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger(__name__)
        self.logger.info(
            f"Initializing Trading Memory MCP Server v{settings.MCP_SERVER_VERSION} ({settings.MCP_SERVER_NAME})"
        )

        self.memory_store = MemoryStore()
        self.get_current_bias_tool = GetCurrentBiasTool(self.memory_store)
        self.store_trading_decision_tool = StoreTradingDecisionTool(self.memory_store)
        self.check_consistency_tool = CheckConsistencyTool(self.memory_store)
        self.force_reset_tool = ForceResetTool(self.memory_store)

        self.server_start_time = time.time()
        self.server_ready = False
        self.server_healthy = False
        self.app = FastMCP(settings.MCP_SERVER_NAME)

        self._register_tools()

    def _register_tools(self):
        @self.app.tool()
        async def get_current_bias(symbol: str) -> Dict[str, Any]:
            if not self.server_ready:
                self.logger.warning("Tool get_current_bias called before server ready")
                return {
                    "error": "server_not_ready",
                    "message": "Server is still initializing",
                    "fallback": "Wait for server to be ready and retry"
                }

            try:
                start_time = time.time()
                result = await self.get_current_bias_tool.execute({"symbol": symbol})
                execution_time = time.time() - start_time

                self.logger.info(
                    f"Tool get_current_bias completed for {symbol} in {round(execution_time * 1000, 2)}ms"
                )
                return result

            except Exception as e:
                execution_time = time.time() - start_time
                self.logger.error(
                    f"Tool get_current_bias failed for {symbol} in {round(execution_time * 1000, 2)}ms: {e}",
                    exc_info=True
                )
                return {
                    "error": "tool_execution_failed",
                    "message": f"Failed to retrieve bias for {symbol}: {str(e)}",
                    "fallback": "Continue without memory context"
                }

        @self.app.tool()
        async def store_trading_decision(symbol: str, decision_type: str, content: Dict[str, Any]) -> Dict[str, Any]:
            if not self.server_ready:
                self.logger.warning("Tool store_trading_decision called before server ready")
                return {
                    "success": False,
                    "error": "server_not_ready",
                    "message": "Server is still initializing",
                }

            try:
                start_time = time.time()
                result = await self.store_trading_decision_tool.execute({
                    "symbol": symbol,
                    "decision_type": decision_type,
                    "content": content,
                })
                execution_time = time.time() - start_time

                self.logger.info(
                    f"Tool store_trading_decision completed for {symbol} ({decision_type}) in {round(execution_time * 1000, 2)}ms"
                )
                return result

            except Exception as e:
                execution_time = time.time() - start_time
                self.logger.error(
                    f"Tool store_trading_decision failed for {symbol} ({decision_type}) in {round(execution_time * 1000, 2)}ms: {e}",
                    exc_info=True
                )
                return {
                    "success": False,
                    "error": "tool_execution_failed",
                    "message": f"Failed to store decision: {str(e)}",
                }

        @self.app.tool()
        async def check_consistency(symbol: str, proposed_bias: str, reasoning: str,
                                    proposed_action: Optional[str] = None,
                                    override_time_gate: bool = False,
                                    market_condition: str = "normal",
                                    current_price: Optional[float] = None) -> Dict[str, Any]:
            if not self.server_ready:
                self.logger.warning("Tool check_consistency called before server ready")
                return {
                    "consistent": False,
                    "conflicts": [{
                        "type": "server_not_ready",
                        "severity": "high",
                        "message": "Server is still initializing",
                    }],
                    "recommendation": "wait_for_server",
                    "guidance": "Wait for server to be ready and retry",
                }

            try:
                start_time = time.time()
                result = await self.check_consistency_tool.execute({
                    "symbol": symbol,
                    "proposed_bias": proposed_bias,
                    "reasoning": reasoning,
                    "proposed_action": proposed_action,
                    "override_time_gate": override_time_gate,
                    "market_condition": market_condition,
                    "current_price": current_price,
                })
                execution_time = time.time() - start_time

                self.logger.info(
                    f"Tool check_consistency completed for {symbol} ({proposed_bias}) in {round(execution_time * 1000, 2)}ms - consistent: {result.get('consistent', False)}"
                )
                return result

            except Exception as e:
                execution_time = time.time() - start_time
                self.logger.error(
                    f"Tool check_consistency failed for {symbol} ({proposed_bias}) in {round(execution_time * 1000, 2)}ms: {e}",
                    exc_info=True
                )
                return {
                    "consistent": False,
                    "conflicts": [{
                        "type": "tool_execution_error",
                        "severity": "high",
                        "message": f"Consistency check failed: {str(e)}",
                    }],
                    "recommendation": "retry_or_proceed_with_caution",
                    "guidance": "Tool execution failed, consider manual override or retry",
                }

        @self.app.tool()
        async def force_reset(symbol: str, confirm: bool, reason: str) -> Dict[str, Any]:
            if not self.server_ready:
                self.logger.warning("Tool force_reset called before server ready")
                return {
                    "success": False,
                    "error": "server_not_ready",
                    "message": "Server is still initializing",
                }

            try:
                start_time = time.time()
                result = await self.force_reset_tool.execute({
                    "symbol": symbol,
                    "confirm": confirm,
                    "reason": reason,
                })
                execution_time = time.time() - start_time

                self.logger.info(
                    f"Tool force_reset completed for {symbol} in {round(execution_time * 1000, 2)}ms"
                )
                return result

            except Exception as e:
                execution_time = time.time() - start_time
                self.logger.error(
                    f"Tool force_reset failed for {symbol} in {round(execution_time * 1000, 2)}ms: {e}",
                    exc_info=True
                )
                return {
                    "success": False,
                    "error": "tool_execution_failed",
                    "message": f"Failed to reset symbol: {str(e)}",
                }

        @self.app.tool()
        async def health_check() -> Dict[str, Any]:
            try:
                redis_healthy = await self.memory_store.health_check()
                uptime_seconds = time.time() - self.server_start_time
                healthy = self.server_ready and redis_healthy

                return {
                    "status": "healthy" if healthy else "unhealthy",
                    "server_ready": self.server_ready,
                    "redis_healthy": redis_healthy,
                    "uptime_seconds": round(uptime_seconds, 2),
                    "timestamp": time.time(),
                    "version": settings.MCP_SERVER_VERSION,
                    "server_name": settings.MCP_SERVER_NAME,
                }
            except Exception as e:
                self.logger.error(f"Health check failed: {e}", exc_info=True)
                return {
                    "status": "error",
                    "error": str(e),
                    "timestamp": time.time(),
                }

    async def startup(self):
        self.logger.info("Starting Trading Memory MCP Server")
        await self.memory_store.initialize()
        self.logger.info("Memory store initialized successfully")
        redis_healthy = await self.memory_store.health_check()
        self.server_ready = True
        self.server_healthy = redis_healthy

    async def shutdown(self):
        self.logger.info("Shutting down Trading Memory MCP Server")
        self.server_ready = False
        self.server_healthy = False
        await self.memory_store.close()
        self.logger.info("Shutdown complete")

    async def run(self):
        try:
            await self.startup()
            self.logger.info("Server ready to handle requests")
        except Exception as e:
            self.logger.error(f"Startup failed: {e}", exc_info=True)
            await self.shutdown()
            raise


# Create server instance for module-level access
server = TradingMemoryServer()
app = server.app


def create_argument_parser() -> argparse.ArgumentParser:
    """Create command line argument parser."""
    parser = argparse.ArgumentParser(
        description="MCP Trading Memory Server",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f"""
Server Configuration:
  Redis Host: {settings.REDIS_HOST}
  Redis Port: {settings.REDIS_PORT}
  Log Level: {settings.LOG_LEVEL}
  Server Name: {settings.MCP_SERVER_NAME}

Examples:
  python -m src.server
  python -m src.server --config-check
  python -m src.server --health-check
        """
    )
    
    parser.add_argument(
        "--version",
        action="version",
        version=f"MCP Trading Memory Server {settings.MCP_SERVER_VERSION}",
    )
    
    parser.add_argument(
        "--config-check",
        action="store_true",
        help="Check configuration and exit",
    )
    
    parser.add_argument(
        "--health-check",
        action="store_true",
        help="Perform health check and exit",
    )
    
    return parser


def validate_configuration(logger: logging.Logger) -> bool:
    """Validate server configuration."""
    try:
        logger.info("Validating server configuration")
        
        # Basic settings validation
        if not settings.MCP_SERVER_NAME:
            logger.error("MCP server name cannot be empty")
            return False
        
        if not (1 <= settings.REDIS_PORT <= 65535):
            logger.error(f"Invalid Redis port: {settings.REDIS_PORT}")
            return False
        
        if settings.REDIS_HOST in ["", None]:
            logger.error("Redis host cannot be empty")
            return False
        
        # Consistency rules validation
        if settings.TIME_GATE_MINUTES < 1:
            logger.error(f"Time gate minutes must be positive: {settings.TIME_GATE_MINUTES}")
            return False
        
        if settings.WHIPSAW_MAX_CHANGES_PER_HOUR < 1:
            logger.error(f"Max changes per hour must be positive: {settings.WHIPSAW_MAX_CHANGES_PER_HOUR}")
            return False
        
        logger.info(
            f"Configuration validation passed - Server: {settings.MCP_SERVER_NAME}, "
            f"Redis: {settings.REDIS_HOST}:{settings.REDIS_PORT}"
        )
        
        return True
        
    except Exception as e:
        logger.error(f"Configuration validation failed: {e}", exc_info=True)
        return False


async def perform_health_check() -> bool:
    """Perform a health check and return result."""
    try:
        if not server or not server.memory_store:
            print("Server components not initialized")
            return False
        
        # Test Redis connection
        await server.memory_store.initialize()
        redis_healthy = await server.memory_store.health_check()
        await server.memory_store.close()
        
        if redis_healthy:
            print("Health check: PASSED")
            print("  - Redis connection: OK")
            print("  - Server configuration: OK")
            return True
        else:
            print("Health check: FAILED")
            print("  - Redis connection: FAILED")
            return False
            
    except Exception as e:
        print(f"Health check: ERROR - {str(e)}")
        return False


def main() -> None:
    """Main entry point with CLI support."""
    # Parse command line arguments
    parser = create_argument_parser()
    args = parser.parse_args()
    
    # Initialize logging
    logger = logging.getLogger(__name__)
    
    try:
        logger.info(
            f"Starting MCP Trading Memory Server v{settings.MCP_SERVER_VERSION} "
            f"({settings.MCP_SERVER_NAME}) - PID: {os.getpid()}"
        )
        
        # Handle special commands
        if args.config_check:
            logger.info("Performing configuration check")
            if validate_configuration(logger):
                logger.info("Configuration check passed")
                sys.exit(0)
            else:
                logger.error("Configuration check failed")
                sys.exit(1)
        
        if args.health_check:
            logger.info("Performing health check")
            if asyncio.run(perform_health_check()):
                sys.exit(0)
            else:
                sys.exit(1)
        
        # Validate configuration before starting server
        if not validate_configuration(logger):
            logger.error("Configuration validation failed, exiting")
            sys.exit(1)
        
        logger.info("Starting FastMCP server")
        
        # Initialize and run server
        asyncio.run(server.startup())
        app.run()
        
    except KeyboardInterrupt:
        logger.info("Server stopped by user")
        asyncio.run(server.shutdown())
        sys.exit(0)
        
    except Exception as e:
        logger.error(f"Server failed to start: {e}", exc_info=True)
        asyncio.run(server.shutdown())
        sys.exit(1)


if __name__ == "__main__":
    main()
