"""
Volcengine Embedding Transformation
Transforms OpenAI embedding requests to Volcengine format
Supports both text-only and multimodal (text + image) embeddings
"""

from typing import List, Optional, Union, Dict, Any
import os
import httpx
from litellm.types.llms.openai import AllEmbeddingInputValues, AllMessageValues
from litellm.types.utils import EmbeddingResponse, Embedding, Usage
from litellm.litellm_core_utils.litellm_logging import Logging as LiteLLMLoggingObj
from litellm.llms.base_llm.embedding.transformation import BaseEmbeddingConfig
from litellm.llms.base_llm.chat.transformation import BaseLLMException
from ..common_utils import get_volcengine_base_url, get_volcengine_headers, VolcEngineError


class VolcEngineEmbeddingConfig(BaseEmbeddingConfig):
    """
    Configuration class for Volcengine embedding models.
    Supports both text-only and multimodal embeddings.
    
    References:
    - Text embeddings: https://ark.cn-beijing.volces.com/api/v3/embeddings
    - Multimodal embeddings: https://www.volcengine.com/docs/82379/1409291
    """

    def __init__(
        self,
        encoding_format: Optional[str] = None,
    ) -> None:
        locals_ = locals().copy()
        for key, value in locals_.items():
            if key != "self" and value is not None:
                setattr(self.__class__, key, value)
        
        # Initialize Volcengine SDK client for multimodal support
        self.api_key = os.environ.get("ARK_API_KEY") or os.environ.get("VOLCENGINE_API_KEY")
        self.client = None
        if self.api_key:
            try:
                from volcenginesdkarkruntime import Ark
                self.client = Ark(api_key=self.api_key)
            except ImportError:
                # SDK not installed, multimodal support will be disabled
                pass

    @classmethod
    def get_config(cls):
        return super().get_config()

    def get_supported_openai_params(self, model: str) -> List[str]:
        """
        Get the list of OpenAI parameters supported by Volcengine embedding models.

        Args:
            model: The model name

        Returns:
            List of supported parameter names
        """
        return [
            "encoding_format",
            "user",
            "extra_headers",
        ]

    def get_complete_url(
        self,
        api_base: Optional[str],
        api_key: Optional[str],
        model: str,
        optional_params: dict,
        litellm_params: dict,
        stream: Optional[bool] = None,
    ) -> str:
        """
        Get the complete URL for volcengine embedding API calls.

        Args:
            api_base: Optional custom API base URL
            api_key: API key (not used for URL construction)
            model: Model name (not used for URL construction)
            optional_params: Optional parameters (not used for URL construction)
            litellm_params: LiteLLM parameters (not used for URL construction)
            stream: Stream parameter (not used for URL construction)

        Returns:
            Complete URL for the embedding API endpoint
        """
        base_url = get_volcengine_base_url(api_base)
        # Construct the complete URL with /embeddings endpoint
        if base_url.endswith("/api/v3"):
            return f"{base_url}/embeddings"
        else:
            return f"{base_url}/api/v3/embeddings"

    def map_openai_params(
        self,
        non_default_params: Dict[str, Any],
        optional_params: Dict[str, Any],
        model: str,
        drop_params: bool,
    ) -> Dict[str, Any]:
        """
        Map OpenAI embedding parameters to Volcengine format.

        Args:
            non_default_params: Parameters that are not default values
            optional_params: Optional parameters dict to update
            model: The model name
            drop_params: Whether to drop unsupported parameters

        Returns:
            Updated optional_params dict
        """
        for param, value in non_default_params.items():
            if param == "encoding_format":
                # Volcengine supports: float, base64, null
                if value in ["float", "base64", None]:
                    optional_params["encoding_format"] = value
                else:
                    if not drop_params:
                        raise ValueError(
                            f"Unsupported encoding_format: {value}. Volcengine supports: float, base64, null"
                        )
            elif param == "user":
                # Keep user parameter as-is
                optional_params["user"] = value
            elif param in self.get_supported_openai_params(model):
                optional_params[param] = value
            elif not drop_params:
                raise ValueError(f"Unsupported parameter for Volcengine: {param}")

        return optional_params

    def transform_embedding_request(
        self,
        model: str,
        input: AllEmbeddingInputValues,
        optional_params: dict,
        headers: dict,
    ) -> dict:
        """Transform embedding request to Volcengine format"""
        # Prepare request data (only the JSON body, not the full request)
        data = {
            "model": model,
            "input": input if isinstance(input, list) else [input],
        }

        # Add optional parameters from optional_params
        if "encoding_format" in optional_params:
            encoding_format = optional_params["encoding_format"]
            if encoding_format is not None:
                data["encoding_format"] = encoding_format

        if "user" in optional_params:
            user = optional_params["user"]
            if user is not None:
                data["user"] = user

        return data

    def transform_embedding_response(
        self,
        model: str,
        raw_response: httpx.Response,
        model_response: EmbeddingResponse,
        logging_obj: LiteLLMLoggingObj,
        api_key: Optional[str],
        request_data: dict,
        optional_params: dict,
        litellm_params: dict,
    ) -> EmbeddingResponse:
        """Transform Volcengine response to EmbeddingResponse"""
        try:
            response_json = raw_response.json()
        except Exception as e:
            raise ValueError(f"Failed to parse Volcengine response as JSON: {str(e)}")

        # Volcengine response format matches OpenAI format closely
        # Just need to ensure all required fields are present
        transformed_response = {
            "object": "list",
            "data": response_json.get("data", []),
            "model": response_json.get("model", model),
            "usage": response_json.get("usage", {}),
        }

        # Add id if present
        if "id" in response_json:
            transformed_response["id"] = response_json["id"]

        # Create EmbeddingResponse from transformed data
        return EmbeddingResponse(**transformed_response)

    def validate_environment(
        self,
        headers: dict,
        model: str,
        messages: List[AllMessageValues],
        optional_params: dict,
        litellm_params: dict,
        api_key: Optional[str] = None,
        api_base: Optional[str] = None,
    ) -> dict:
        """Validate environment and return headers"""
        # Get Volcengine headers
        if api_key is None:
            raise ValueError("api_key is required for Volcengine authentication")
        volcengine_headers = get_volcengine_headers(api_key)
        return {**headers, **volcengine_headers}

    def get_error_class(
        self, error_message: str, status_code: int, headers: Union[dict, httpx.Headers]
    ) -> BaseLLMException:
        """Get error class for Volcengine errors"""
        from ..common_utils import VolcEngineError

        # Convert dict to httpx.Headers if needed
        if isinstance(headers, dict):
            headers = httpx.Headers(headers)
        return VolcEngineError(
            status_code=status_code,
            message=error_message,
            headers=headers,
        )

    # ==================== Multimodal Embedding Support ====================

    def _is_multimodal_input(self, input: Any) -> bool:
        """
        Detect whether input is text-only or multimodal (text + image).
        
        Args:
            input: The input to analyze (str, list, or dict)
            
        Returns:
            True if input contains image URLs, False otherwise
        """
        if isinstance(input, str):
            # Check if it's an image URL
            return input.startswith(("http://", "https://", "data:image/"))
        elif isinstance(input, list):
            # Check if it's already in multimodal format
            if input and isinstance(input[0], dict) and "type" in input[0]:
                return True  # Already in multimodal format
            # Check if any element is an image URL
            for item in input:
                if isinstance(item, str) and item.startswith(("http://", "https://", "data:image/")):
                    return True
        return False

    def _transform_multimodal_input(self, input: Any) -> List[Dict[str, Any]]:
        """
        Transform LiteLLM input to Volcengine multimodal format.
        
        Args:
            input: Input in various formats (str, list of str, or list of dict)
            
        Returns:
            List of dicts in Volcengine multimodal format
            
        Examples:
            >>> self._transform_multimodal_input("hello")
            [{"type": "text", "text": "hello"}]
            
            >>> self._transform_multimodal_input("https://example.com/image.jpg")
            [{"type": "image_url", "image_url": {"url": "https://example.com/image.jpg"}}]
            
            >>> self._transform_multimodal_input(["hello", "https://example.com/image.jpg"])
            [{"type": "text", "text": "hello"}, {"type": "image_url", "image_url": {"url": "https://example.com/image.jpg"}}]
        """
        if isinstance(input, str):
            # Single string
            if input.startswith(("http://", "https://", "data:image/")):
                return [{"type": "image_url", "image_url": {"url": input}}]
            else:
                return [{"type": "text", "text": input}]
        
        elif isinstance(input, list):
            # List input
            if not input:
                return []
            
            # Check if already in multimodal format
            if isinstance(input[0], dict) and "type" in input[0]:
                return input  # Already in correct format
            
            # Transform string list to multimodal format
            result = []
            for item in input:
                if isinstance(item, str):
                    if item.startswith(("http://", "https://", "data:image/")):
                        result.append({"type": "image_url", "image_url": {"url": item}})
                    else:
                        result.append({"type": "text", "text": item})
                else:
                    raise ValueError(f"Unsupported list item type: {type(item)}. Expected string or dict.")
            return result
        
        else:
            raise ValueError(f"Unsupported input type: {type(input)}. Expected str or list.")

    def _transform_multimodal_response(self, resp: Any) -> EmbeddingResponse:
        """
        Transform Volcengine multimodal embedding response to LiteLLM format.
        
        Args:
            resp: Volcengine API response (dict-like)
            
        Returns:
            EmbeddingResponse in LiteLLM standard format
        """
        # Handle response object or dict
        if hasattr(resp, "get"):
            data = resp.get("data", [])
            model = resp.get("model", "")
            usage_data = resp.get("usage", {})
            obj = resp.get("object", "list")
            resp_id = resp.get("id")
        else:
            data = resp.get("data", []) if isinstance(resp, dict) else []
            model = resp.get("model", "") if isinstance(resp, dict) else ""
            usage_data = resp.get("usage", {}) if isinstance(resp, dict) else {}
            obj = resp.get("object", "list") if isinstance(resp, dict) else "list"
            resp_id = resp.get("id") if isinstance(resp, dict) else None
        
        # Transform data array to Embeddings objects
        embeddings_list = []
        for idx, item in enumerate(data):
            embedding_vector = item.get("embedding", [])
            if isinstance(embedding_vector, dict) and "embedding" in embedding_vector:
                # Handle nested embedding structure
                embedding_vector = embedding_vector["embedding"]
            
            embeddings_list.append(
                Embedding(
                    object="embedding",
                    embedding=embedding_vector,
                    index=item.get("index", idx),
                )
            )
        
        # Transform usage data
        usage = Usage(
            prompt_tokens=usage_data.get("prompt_tokens", 0),
            completion_tokens=usage_data.get("completion_tokens", 0),
            total_tokens=usage_data.get("total_tokens", 0),
        )
        
        # Build transformed response
        transformed_response = {
            "object": obj,
            "data": embeddings_list,
            "model": model,
            "usage": usage,
        }
        
        if resp_id:
            transformed_response["id"] = resp_id
        
        return EmbeddingResponse(**transformed_response)

    async def _multimodal_embedding(
        self,
        model: str,
        input: Any,
        optional_params: Optional[Dict[str, Any]] = None,
        logging_obj: Optional[LiteLLMLoggingObj] = None,
        api_key: Optional[str] = None,
        api_base: Optional[str] = None,
        timeout: Optional[float] = None,
    ) -> EmbeddingResponse:
        """
        Generate multimodal embeddings using Volcengine's multimodal_embeddings API.
        
        Args:
            model: Model identifier (e.g., "volcengine/ep-20260130160935-ktvl4")
            input: Input data (text, image, or mixed)
            optional_params: Optional parameters
            logging_obj: Logging object
            api_key: API key for authentication
            api_base: Custom API base URL
            timeout: Request timeout
            
        Returns:
            EmbeddingResponse with embeddings and usage metrics
            
        Raises:
            ValueError: If SDK not installed or input is invalid
            VolcEngineError: If Volcengine API call fails
        """
        # Check if SDK client is available
        if self.client is None:
            from volcenginesdkarkruntime import Ark
            try:
                self.client = Ark(api_key=self.api_key)
            except ImportError:
                raise ValueError(
                    "volcenginesdkarkruntime SDK is required for multimodal embeddings. "
                    "Install it with: pip install 'volcengine-python-sdk[ark]'"
                )
        
        # Transform input to Volcengine format
        volcengine_input = self._transform_multimodal_input(input)
        
        # Extract endpoint ID (remove "volcengine/" prefix if present)
        endpoint_id = model.split("/")[-1] if "/" in model else model
        
        try:
            # Call Volcengine multimodal embeddings API
            # Note: The SDK may not support async directly, so we use asyncio.to_thread
            import asyncio
            
            resp = await asyncio.to_thread(
                self.client.multimodal_embeddings.create,
                model=endpoint_id,
                input=volcengine_input,
            )
        except Exception as e:
            # Convert to Volcengine error
            status_code = getattr(e, "status_code", 500)
            error_message = str(e)
            raise VolcEngineError(
                status_code=status_code,
                message=f"Volcengine multimodal embeddings API error: {error_message}",
            )
        
        # Transform response
        return self._transform_multimodal_response(resp)

    async def aembedding(
        self,
        model: str,
        input: AllEmbeddingInputValues,
        optional_params: Optional[dict] = None,
        encoding_format: Optional[str] = None,
        user: Optional[str] = None,
        extra_headers: Optional[dict] = None,
        logging_obj: Optional[LiteLLMLoggingObj] = None,
        api_key: Optional[str] = None,
        api_base: Optional[str] = None,
        timeout: Optional[float] = None,
    ) -> EmbeddingResponse:
        """
        Async embedding generation with multimodal support.
        
        Route to multimodal or text-only embedding based on input type.
        
        Args:
            model: Model identifier
            input: Input data
            optional_params: Optional parameters
            encoding_format: Encoding format
            user: User identifier
            extra_headers: Extra headers
            logging_obj: Logging object
            api_key: API key for authentication
            api_base: Custom API base URL
            timeout: Request timeout
            
        Returns:
            EmbeddingResponse with embeddings
            
        Note:
            This method routes to multimodal embedding if input contains image URLs,
            otherwise it uses the standard text embedding path.
        """
        # Check if input is multimodal
        if self._is_multimodal_input(input):
            # Use multimodal embedding path
            return await self._multimodal_embedding(
                model=model,
                input=input,
                optional_params=optional_params,
                logging_obj=logging_obj,
                api_key=api_key,
                api_base=api_base,
                timeout=timeout,
            )
        else:
            # Use standard text embedding path (existing logic)
            return await super().aembedding(
                model=model,
                input=input,
                optional_params=optional_params,
                encoding_format=encoding_format,
                user=user,
                extra_headers=extra_headers,
                logging_obj=logging_obj,
                api_key=api_key,
                api_base=api_base,
                timeout=timeout,
            )
