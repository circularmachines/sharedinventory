#!/usr/bin/env python3
"""
AI API Call module for making structured calls to AI models.

This script takes a list of messages formatted for OpenAI API,
makes the API call, and returns structured output using Pydantic models.

Usage:
    Import the AIApiCaller class and use it to make API calls
    or run directly with a JSON file containing messages.
    
    python ai_api_call.py --input data/processed_videos/prompt.json
"""

import os
import sys
import json
import logging
import argparse
from typing import List, Dict, Any, Optional, Union
from pathlib import Path
from dotenv import load_dotenv

from openai import AzureOpenAI
from pydantic import BaseModel, Field

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name%s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Load environment variables from .env file
load_dotenv()



# Define Pydantic models for structured response
class AIResponse(BaseModel):
    """Base model for AI API response"""
    response: str = Field(..., description="Follow instructions for response")
    list_of_keywords: List[str] = Field(..., description="A list of relevant keywords extracted from the content")


class AIApiCaller:
    """Class to handle AI API calls with structured responses"""
    
    def __init__(self, 
                 api_key: Optional[str] = None,
                 azure_endpoint: Optional[str] = None,
                 api_version: Optional[str] = None,
                 deployment_name: Optional[str] = None):
        """Initialize the AI API caller with credentials"""
        self.logger = logging.getLogger(__name__ + ".AIApiCaller")
        
        # Use provided credentials or try to load from environment variables
        # Check multiple possible environment variable names for API key
        self.api_key = api_key or os.getenv("GPT_API_KEY") or os.getenv("WHISPER_API_KEY")
        self.azure_endpoint = azure_endpoint or os.getenv("AZURE_OPENAI_ENDPOINT")
        self.api_version = api_version or os.getenv("GPT_API_VERSION") or os.getenv("WHISPER_API_VERSION", "2023-05-15")
        self.deployment_name = deployment_name or os.getenv("GPT_DEPLOYMENT_NAME", "gpt-4")
        
        # Debug information
        self.logger.debug(f"Azure Endpoint: {self.azure_endpoint}")
        self.logger.debug(f"API Version: {self.api_version}")
        self.logger.debug(f"Model Deployment: {self.deployment_name}")
        
        # Initialize client if credentials are available
        self.client = None
        if self.api_key and self.azure_endpoint:
            self.logger.info("Initializing Azure OpenAI client")
            try:
                self.client = AzureOpenAI(
                    api_key=self.api_key,
                    azure_endpoint=self.azure_endpoint,
                    api_version=self.api_version
                )
                self.logger.info("Azure OpenAI client initialized successfully")
            except Exception as e:
                self.logger.error(f"Failed to initialize Azure OpenAI client: {str(e)}")
                self.logger.error(f"Error details: {e}")
        else:
            missing = []
            if not self.api_key:
                missing.append("API_KEY (checked GPT_API_KEY, WHISPER_API_KEY)")
            if not self.azure_endpoint:
                missing.append("AZURE_OPENAI_ENDPOINT")
            self.logger.warning(f"Azure OpenAI credentials not provided: missing {', '.join(missing)}")
    
    def _sanitize_messages(self, messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Sanitize messages to ensure they can be properly processed by the API
        Particularly handles image content to avoid logging large base64 strings
        """
        sanitized = []
        for msg in messages:
            if isinstance(msg.get('content'), list):
                # If content is a list (multimodal), handle each item
                safe_content = []
                for item in msg['content']:
                    if item.get('type') == 'image_url' and isinstance(item.get('image_url'), dict):
                        # For image URLs, truncate the URL for logging
                        url = item['image_url'].get('url', '')
                        if url.startswith('data:'):
                            # For base64, just indicate presence instead of logging the data
                            safe_content.append({'type': 'image_url', 'image_url': {'url': f'data:[...truncated, length: {len(url)}]'}})
                        else:
                            # For regular URLs, keep them intact
                            safe_content.append(item)
                    else:
                        # For non-image content, keep it as is
                        safe_content.append(item)
                sanitized.append({**msg, 'content': safe_content})
            else:
                # For regular text content, keep it as is
                sanitized.append(msg)
        return sanitized
    
    def call_ai_api(self, messages: List[Dict[str, Any]], response_model: type = AIResponse) -> Dict[str, Any]:
        """
        Call AI API with the provided messages and return structured response
        
        Args:
            messages: List of message dictionaries with role and content
            response_model: Pydantic model for the response structure
            
        Returns:
            Dictionary containing the structured response
        """
        if not self.client:
            self.logger.error("Cannot call AI API without initialized client")
            return {"error": "AI client not initialized"}
            
        self.logger.info(f"Calling AI API with {len(messages)} messages")
        
        try:
            # Debug: print sanitized messages
            sanitized_messages = self._sanitize_messages(messages)
            self.logger.debug(f"Sanitized messages: {json.dumps(sanitized_messages, indent=2)}")
            
            # Make API call with Pydantic model-defined response format
            self.logger.info(f"Using model deployment: {self.deployment_name}")
            
            # First try the beta.parse approach
            try:
                self.logger.info("Attempting to use beta.chat.completions.parse")
                completion = self.client.beta.chat.completions.parse(
                    model=self.deployment_name,
                    messages=messages,
                    response_format=response_model,
                )
                
                self.logger.info("Received response from AI API using parse method")
                
                # Access the parsed response directly
                response = completion.choices[0].message.parsed
                
                if response:
                    # Return the model as a dictionary
                    result = response.model_dump()
                    self.logger.info("Successfully parsed structured response")
                    self.logger.debug(f"Response: {result}")
                    return result
                else:
                    # Handle case where parsing failed due to model refusal
                    refusal = getattr(completion.choices[0].message, 'refusal', 'No specific refusal message')
                    self.logger.error(f"Model refused to provide structured response: {refusal}")
                    return {"error": "Model refusal", "message": str(refusal)}
                
            except AttributeError as ae:
                # If beta.parse isn't available, fall back to standard approach
                self.logger.warning(f"beta.parse not available: {ae}. Falling back to standard completion with JSON format")
                return self._fallback_completion(messages)
                
            except Exception as e:
                self.logger.warning(f"Error using parse method: {e}. Falling back to standard completion.")
                return self._fallback_completion(messages)
            
        except Exception as e:
            self.logger.error(f"Error calling AI API: {str(e)}")
            return {"error": str(e)}
    
    def _fallback_completion(self, messages: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Fall back to standard completion with JSON response format
        """
        try:
            # Start with system message to ensure proper formatting
            updated_messages = self._add_json_instructions(messages)
            
            self.logger.info("Using standard chat.completions.create with JSON format")
            response = self.client.chat.completions.create(
                model=self.deployment_name,
                messages=updated_messages,
                response_format={"type": "json_object"},
                temperature=0.7,
                max_tokens=1000
            )
            
            self.logger.info("Received response from AI API")
            
            # Parse response content as JSON
            response_content = response.choices[0].message.content
            self.logger.debug(f"Raw response content: {response_content[:200]}...")
            
            # Parse the JSON response
            try:
                result = json.loads(response_content)
                self.logger.info("Successfully parsed JSON response")
                return result
            except json.JSONDecodeError as je:
                self.logger.error(f"Failed to parse response as JSON: {je}")
                return {"error": "Invalid JSON response", "raw_response": response_content}
                
        except Exception as e:
            self.logger.error(f"Error in fallback completion: {str(e)}")
            return {"error": str(e)}
    
    def _add_json_instructions(self, messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Add JSON format instructions to system message
        """
        updated_messages = []
        system_found = False
        
        for msg in messages:
            if msg["role"] == "system":
                system_found = True
                # Add JSON instructions to system message
                content = msg["content"]
                if isinstance(content, str):
                    json_instructions = (
                        f"{content} "
                        f"Your response must be a valid JSON object with the following structure: "
                        f"{{'friendly_response': 'your response text here', "
                        f"'list_of_keywords': ['keyword1', 'keyword2', ...]}}"
                    )
                    updated_messages.append({"role": "system", "content": json_instructions})
                else:
                    # If content is not a string, keep it as is
                    updated_messages.append(msg)
            else:
                updated_messages.append(msg)
        
        # Add a system message if none exists
        if not system_found:
            json_instructions = (
                "You are a helpful assistant. Analyze the provided content and respond accordingly. "
                "Your response must be a valid JSON object with the following structure: "
                "{'friendly_response': 'your response text here', "
                "'list_of_keywords': ['keyword1', 'keyword2', ...]}"
            )
            updated_messages.insert(0, {"role": "system", "content": json_instructions})
        
        return updated_messages


def load_messages(file_path: str) -> List[Dict[str, Any]]:
    """Load messages from a JSON file"""
    try:
        logger.info(f"Loading messages from {file_path}")
        with open(file_path, 'r') as f:
            messages = json.load(f)
        logger.info(f"Loaded {len(messages)} messages")
        return messages
    except Exception as e:
        logger.error(f"Error loading messages: {str(e)}")
        return []

def main():
    """Main function with hardcoded example"""
    example_input = "data/processed_videos/prompt.json"
    logger.info(f"Using example input file: {example_input}")
    
    # Load messages from file
    messages = load_messages(example_input)
    if not messages:
        logger.error("No messages loaded, exiting")
        return 1
        
    # Create API caller
    api_caller = AIApiCaller()
    
    # Make API call with debug enabled
    response = api_caller.call_ai_api(messages)
    
    if response:
        print(f"\nAI API call successful:")
        print(json.dumps(response, indent=2))  # Clean output for piping
    else:
        print("\nFailed to get AI response")
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())