"""Simple smoke tests for the trading memory system."""

import unittest
from unittest.mock import AsyncMock, MagicMock

from src.tools.get_current_bias import GetCurrentBiasTool
from src.tools.store_trading_decision import StoreTradingDecisionTool
from src.tools.check_consistency import CheckConsistencyTool
from src.tools.force_reset import ForceResetTool


class TestTradeMemory(unittest.TestCase):
    """Simple smoke tests to verify basic functionality."""
    
    def test_tool_imports(self):
        """Test that all tools can be imported."""
        # If we got here, imports worked
        self.assertTrue(True)
    
    def test_tool_descriptions(self):
        """Test that tools have descriptions."""
        mock_store = MagicMock()
        
        bias_tool = GetCurrentBiasTool(mock_store)
        decision_tool = StoreTradingDecisionTool(mock_store) 
        consistency_tool = CheckConsistencyTool(mock_store)
        reset_tool = ForceResetTool(mock_store)
        
        # All tools should have descriptions
        self.assertIsInstance(bias_tool.description, str)
        self.assertIsInstance(decision_tool.description, str)
        self.assertIsInstance(consistency_tool.description, str)
        self.assertIsInstance(reset_tool.description, str)
        
        # Descriptions should not be empty
        self.assertGreater(len(bias_tool.description), 0)
        self.assertGreater(len(decision_tool.description), 0)
        self.assertGreater(len(consistency_tool.description), 0)
        self.assertGreater(len(reset_tool.description), 0)
    
    def test_tool_schemas(self):
        """Test that tools have input schemas."""
        mock_store = MagicMock()
        
        bias_tool = GetCurrentBiasTool(mock_store)
        decision_tool = StoreTradingDecisionTool(mock_store) 
        consistency_tool = CheckConsistencyTool(mock_store)
        reset_tool = ForceResetTool(mock_store)
        
        # All tools should have schemas
        self.assertIsInstance(bias_tool.input_schema, dict)
        self.assertIsInstance(decision_tool.input_schema, dict)
        self.assertIsInstance(consistency_tool.input_schema, dict)
        self.assertIsInstance(reset_tool.input_schema, dict)
        
        # Schemas should have required structure
        for tool in [bias_tool, decision_tool, consistency_tool, reset_tool]:
            schema = tool.input_schema
            self.assertIn("type", schema)
            self.assertIn("properties", schema)
            self.assertEqual(schema["type"], "object")


class TestValidation(unittest.TestCase):
    """Test basic validation without Redis dependencies."""
    
    def test_bias_tool_validation(self):
        """Test bias tool input validation."""
        mock_store = MagicMock()
        tool = GetCurrentBiasTool(mock_store)
        
        # Test symbol validation
        self.assertTrue(tool._validate_symbol("SPY"))
        self.assertTrue(tool._validate_symbol("QQQ"))
        self.assertTrue(tool._validate_symbol("AAPL"))
        
        # Test invalid symbols
        self.assertFalse(tool._validate_symbol(""))
        self.assertFalse(tool._validate_symbol("SP Y"))  # space
        self.assertFalse(tool._validate_symbol("TOOLONGSYMBOL123"))  # too long
        self.assertFalse(tool._validate_symbol(None))
        
        # Note: lowercase "spy" is valid because it gets converted to uppercase internally
    
    def test_decision_tool_validation(self):
        """Test decision tool validation logic."""
        mock_store = MagicMock()
        tool = StoreTradingDecisionTool(mock_store)
        
        # Test bias establishment validation
        valid_content = {
            "bias": "bullish",
            "confidence": 80,
            "reasoning": "Strong technical setup with volume confirmation",
            "invalidation_level": 450.0
        }
        
        result = tool._validate_bias_establishment(valid_content)
        self.assertTrue(result["valid"])
        
        # Test invalid content
        invalid_content = {
            "bias": "invalid",  # bad bias
            "confidence": 80,
            "reasoning": "Short",  # too short
        }
        
        result = tool._validate_bias_establishment(invalid_content)
        self.assertFalse(result["valid"])


if __name__ == '__main__':
    unittest.main()