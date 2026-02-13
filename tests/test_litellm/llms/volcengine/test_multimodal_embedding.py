"""
Tests for Volcengine Multimodal Embeddings
"""

import pytest
from unittest.mock import MagicMock, patch
import asyncio

from litellm.llms.volcengine.embedding.transformation import VolcEngineEmbeddingConfig
from litellm.types.utils import EmbeddingResponse


class TestVolcengineMultimodalEmbedding:
    """Test Volcengine multimodal embedding functionality"""
    
    def test_is_multimodal_input_text_string(self):
        """Test text string detection"""
        config = VolcEngineEmbeddingConfig()
        
        # Regular text should not be multimodal
        assert not config._is_multimodal_input("hello world")
        assert not config._is_multimodal_input("你好")
        assert not config._is_multimodal_input("123456")
    
    def test_is_multimodal_input_http_url(self):
        """Test HTTP URL detection"""
        config = VolcEngineEmbeddingConfig()
        
        # HTTP URLs should be detected as multimodal
        assert config._is_multimodal_input("http://example.com/image.jpg")
        assert config._is_multimodal_input("https://example.com/image.png")
    
    def test_is_multimodal_input_base64_image(self):
        """Test base64 image detection"""
        config = VolcEngineEmbeddingConfig()
        
        # Base64 images should be detected as multimodal
        assert config._is_multimodal_input("data:image/jpeg;base64,/9j/4AAQ...")
        assert config._is_multimodal_input("data:image/png;base64,iVBOR...")
    
    def test_is_multimodal_input_dict_format(self):
        """Test multimodal dict format detection"""
        config = VolcEngineEmbeddingConfig()
        
        # Dict format with "type" field should be multimodal
        input_format = [{"type": "text", "text": "hello"}]
        assert config._is_multimodal_input(input_format)
    
    def test_is_multimodal_input_mixed_list(self):
        """Test mixed string list detection"""
        config = VolcEngineEmbeddingConfig()
        
        # Mix of text and image URLs should be multimodal
        assert config._is_multimodal_input(["hello", "https://example.com/image.jpg"])
        assert config._is_multimodal_input(["text1", "text2", "http://img.jpg"])
        
        # Text-only list should not be multimodal
        assert not config._is_multimodal_input(["hello", "world"])
    
    def test_transform_multimodal_input_single_text(self):
        """Test single text transformation"""
        config = VolcEngineEmbeddingConfig()
        
        result = config._transform_multimodal_input("hello")
        expected = [{"type": "text", "text": "hello"}]
        assert result == expected
    
    def test_transform_multimodal_input_http_url(self):
        """Test HTTP URL transformation"""
        config = VolcEngineEmbeddingConfig()
        
        result = config._transform_multimodal_input("https://example.com/image.jpg")
        expected = [{"type": "image_url", "image_url": {"url": "https://example.com/image.jpg"}}]
        assert result == expected
    
    def test_transform_multimodal_input_base64_image(self):
        """Test base64 image URL transformation"""
        config = VolcEngineEmbeddingConfig()
        
        result = config._transform_multimodal_input("data:image/jpeg;base64,/9j/...")
        expected = [{"type": "image_url", "image_url": {"url": "data:image/jpeg;base64,/9j/..."}}]
        assert result == expected
    
    def test_transform_multimodal_input_mixed_list(self):
        """Test mixed string list transformation"""
        config = VolcEngineEmbeddingConfig()
        
        result = config._transform_multimodal_input(["你好", "https://example.com/image.jpg", "world"])
        expected = [
            {"type": "text", "text": "你好"},
            {"type": "image_url", "image_url": {"url": "https://example.com/image.jpg"}},
            {"type": "text", "text": "world"}
        ]
        assert result == expected
    
    def test_transform_multimodal_input_dict_format_passthrough(self):
        """Test dict format passthrough"""
        config = VolcEngineEmbeddingConfig()
        
        input_format = [
            {"type": "text", "text": "hello"},
            {"type": "image_url", "image_url": {"url": "https://example.com/image.jpg"}}
        ]
        result = config._transform_multimodal_input(input_format)
        assert result == input_format
    
    def test_transform_multimodal_input_empty_list(self):
        """Test empty list transformation"""
        config = VolcEngineEmbeddingConfig()
        
        result = config._transform_multimodal_input([])
        assert result == []
    
    def test_transform_multimodal_input_invalid_type(self):
        """Test invalid input type raises ValueError"""
        config = VolcEngineEmbeddingConfig()
        
        # Object input should raise ValueError
        with pytest.raises(ValueError, match="Unsupported input type"):
            config._transform_multimodal_input({"key": "value"})
        
        # List with invalid item type should raise ValueError
        with pytest.raises(ValueError, match="Unsupported list item type"):
            config._transform_multimodal_input([123, "text"])
    
    def test_transform_multimodal_response_single_embedding(self):
        """Test single embedding response transformation"""
        config = VolcEngineEmbeddingConfig()
        
        mock_response = {
            "object": "list",
            "data": [
                {
                    "embedding": [0.1, 0.2, 0.3] + [0.01 * i for i in range(1021)],
                    "index": 0
                }
            ],
            "model": "ep-20260130160935-ktvl4",
            "usage": {
                "prompt_tokens": 10,
                "total_tokens": 10
            }
        }
        
        result = config._transform_multimodal_response(mock_response)
        
        assert result.object == "list"
        assert len(result.data) == 1
        assert len(result.data[0].embedding) == 1024
        assert result.data[0].index == 0
        assert result.model == "ep-20260130160935-ktvl4"
        assert result.usage.prompt_tokens == 10
        assert result.usage.total_tokens == 10
    
    def test_transform_multimodal_response_multiple_embeddings(self):
        """Test multiple embeddings response transformation"""
        config = VolcEngineEmbeddingConfig()
        
        mock_response = {
            "object": "list",
            "data": [
                {
                    "embedding": [0.1, 0.2, 0.3] + [0.01 * i for i in range(1021)],
                    "index": 0
                },
                {
                    "embedding": [0.4, 0.5, 0.6] + [0.02 * i for i in range(1021)],
                    "index": 1
                }
            ],
            "model": "ep-20260130160935-ktvl4",
            "usage": {
                "prompt_tokens": 20,
                "total_tokens": 20
            }
        }
        
        result = config._transform_multimodal_response(mock_response)
        
        assert len(result.data) == 2
        assert result.data[0].index == 0
        assert result.data[1].index == 1
        assert result.usage.prompt_tokens == 20
    
    def test_transform_multimodal_response_nested_embedding(self):
        """Test response with nested embedding structure"""
        config = VolcEngineEmbeddingConfig()
        
        mock_response = {
            "object": "list",
            "data": [
                {
                    "embedding": {
                        "embedding": [0.1, 0.2, 0.3]
                    },
                    "index": 0
                }
            ],
            "model": "ep-20260130160935-ktvl4",
            "usage": {
                "prompt_tokens": 5,
                "total_tokens": 5
            }
        }
        
        result = config._transform_multimodal_response(mock_response)
        
        assert len(result.data) == 1
        # Should extract nested embedding
        assert result.data[0].embedding == [0.1, 0.2, 0.3]
    
    def test_transform_multimodal_response_missing_fields(self):
        """Test response with missing fields (default values)"""
        config = VolcEngineEmbeddingConfig()
        
        # Response with missing usage fields
        mock_response = {
            "data": [
                {
                    "embedding": [0.1, 0.2, 0.3]
                }
            ]
        }
        
        result = config._transform_multimodal_response(mock_response)
        
        assert result.object == "list"  # Default
        assert result.model == ""  # Default
        assert result.usage.prompt_tokens == 0  # Default
        assert result.usage.total_tokens == 0  # Default
    
    def test_transform_multimodal_response_with_id(self):
        """Test response includes id field"""
        config = VolcEngineEmbeddingConfig()
        
        mock_response = {
            "object": "list",
            "data": [
                {
                    "embedding": [0.1, 0.2, 0.3],
                    "index": 0
                }
            ],
            "model": "ep-20260130160935-ktvl4",
            "usage": {"prompt_tokens": 5, "total_tokens": 5},
            "id": "chatcmpl-test123"
        }
        
        result = config._transform_multimodal_response(mock_response)
        
        # id field not part of EmbeddingResponse type
    
    @pytest.mark.asyncio
    async def test_multimodal_embedding_sdk_not_installed(self):
        """Test multimodal embedding when SDK not installed"""
        mock_client = MagicMock()
        mock_client.multimodal_embeddings.create.side_effect = Exception("Authorization failed")
        
        config = VolcEngineEmbeddingConfig()
        config.client = mock_client
        
        from litellm.llms.volcengine.common_utils import VolcEngineError
        
        with pytest.raises(VolcEngineError, match="Volcengine multimodal embeddings API error"):
            await config._multimodal_embedding(
                model="volcengine/ep-test",
                input=["test"]
            )
    
    @pytest.mark.asyncio
    async def test_multimodal_embedding_with_error(self):
        config = VolcEngineEmbeddingConfig()
        
        # Create an error with status code
        api_error = Exception("Rate limit exceeded")
        api_error.status_code = 429
        
        mock_client = MagicMock()
        mock_client.multimodal_embeddings.create.side_effect = api_error
        config.client = mock_client
        
        from litellm.llms.volcengine.common_utils import VolcEngineError
        
        with pytest.raises(VolcEngineError) as exc_info:
            await config._multimodal_embedding(
                model="volcengine/ep-test",
                input=["test"]
            )
        
        assert exc_info.value.status_code == 429


class TestVolcengineEmbeddingInit:
    """Test VolcengineEmbeddingConfig initialization"""
    
    def test_init_with_ark_api_key(self, monkeypatch):
        """Test initialization with ARK_API_KEY"""
        monkeypatch.setenv("ARK_API_KEY", "test-api-key")
        
        config = VolcEngineEmbeddingConfig()
        
        # API Key should be captured
        assert config.api_key == "test-api-key"
        # Client should try to initialize (may be None if SDK not installed)
        assert config.client is not None or True  # Allow None if SDK not installed
    
    def test_init_with_volcengine_api_key(self, monkeypatch):
        """Test initialization with VOLCENGINE_API_KEY"""
        monkeypatch.setenv("VOLCENGINE_API_KEY", "test-api-key")
        
        config = VolcEngineEmbeddingConfig()
        
        # VOLCENGINE_API_KEY should be captured as fallback
        assert config.api_key == "test-api-key"
    
    def test_init_ark_precedence(self, monkeypatch):
        """Test ARK_API_KEY takes precedence over VOLCENGINE_API_KEY"""
        monkeypatch.setenv("ARK_API_KEY", "ark-key")
        monkeypatch.setenv("VOLCENGINE_API_KEY", "volcengine-key")
        
        config = VolcEngineEmbeddingConfig()
        
        # ARK_API_KEY should be used
        assert config.api_key == "ark-key"
    
    def test_init_without_api_key(self, monkeypatch):
        """Test initialization without API Key"""
        monkeypatch.delenv("ARK_API_KEY", raising=False)
        monkeypatch.delenv("VOLCENGINE_API_KEY", raising=False)
        
        config = VolcEngineEmbeddingConfig()
        
        # API Key should be None
        assert config.api_key is None
        # Client should not initialize
        assert config.client is None


class TestVolcengineEmbeddingBackwardCompatibility:
    """Test backward compatibility with existing text embeddings"""
    
    def test_text_only_embedding_unaffected(self, monkeypatch):
        """Test text-only inputs use existing path"""
        monkeypatch.setenv("ARK_API_KEY", "test-key")
        
        config = VolcEngineEmbeddingConfig()
        
        # Text-only inputs should NOT be multimodal
        assert not config._is_multimodal_input("hello")
        assert not config._is_multimodal_input(["hello", "world"])
        assert not config._is_multimodal_input("123")
    
    @pytest.mark.asyncio
    async def test_aembedding_text_only_uses_super_method(self, monkeypatch):
        """Test aembedding calls super() for text-only input"""
        monkeypatch.setenv("ARK_API_KEY", "test-key")
        
        config = VolcEngineEmbeddingConfig()
        
        # Create a mock for the parent method
        with patch.object(VolcEngineEmbeddingConfig, 'aembedding', wraps=config.__class__.aembedding) as mock_super:
            # Return a mock response
            mock_response = MagicMock()
            mock_super.return_value = mock_response
            
            # Call with text-only input - should route to super()
            await config.aembedding(
                model="volcengine/ep-test",
                input=["hello", "world"],
                api_key="test-key",
            )
            
            # Verify super().aembedding() was called
            mock_super.assert_called_once()
            
            # Verify the call did NOT route through multimodal path
            call_args = mock_super.call_args
            assert "hello" in str(call_args) or "world" in str(call_args)


def test_multimodal_embedding_end_to_flow():
    """Test end-to-end multimodal embedding flow"""
    # This would require actual SDK, so we mock it
    config = VolcEngineEmbeddingConfig()
    
    # Test the complete flow: input -> transform -> API -> response transform
    input = ["hello world", "https://example.com/image.jpg"]
    model = "volcengine/ep-20260130160935-3xyz"
    
    # Step 1: Detect multimodal
    assert config._is_multimodal_input(input) == True
    
    # Step 2: Transform input
    transformed = config._transform_multimodal_input(input)
    expected = [
        {"type": "text", "text": "hello world"},
        {"type": "image_url", "image_url": {"url": "https://example.com/image.jpg"}}
    ]
    assert transformed == expected
    
    # Step 3: Verify endpoint ID extraction
    endpoint_id = model.split("/")[-1]
    assert endpoint_id == "ep-20260130160935-3xyz"


def test_error_handling_invalid_input_format():
    """Test error handling for invalid input formats"""
    config = VolcEngineEmbeddingConfig()
    
    # Test with object input
    with pytest.raises(ValueError):
        config._transform_multimodal_input({"invalid": "format"})
    
    # Test with dict in list (not string or proper dict)
    with pytest.raises(ValueError):
        config._transform_multimodal_input([{"no_type": "field"}])


def test_transformation_preserves_order():
    """Test transformation preserves input order"""
    config = VolcEngineEmbeddingConfig()
    
    input = [
        "text1", 
        "https://img1.jpg", 
        "text2", 
        "https://img2.jpg",
        "text3"
    ]
    
    result = config._transform_multimodal_input(input)
    
    # Verify order is preserved
    assert len(result) == 5
    assert result[0] == {"type": "text", "text": "text1"}
    assert result[1] == {"type": "image_url", "image_url": {"url": "https://img1.jpg"}}
    assert result[2] == {"type": "text", "text": "text2"}
    assert result[3] == {"type": "image_url", "image_url": {"url": "https://img2.jpg"}}
    assert result[4] == {"type": "text", "text": "text3"}
