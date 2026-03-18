"""File download tool using httpx for downloading various file types."""

import os
import uuid
import httpx
from typing import Dict, Optional, Union
from smolagents import Tool

class DownloadTool(Tool):
    """
    A tool for downloading files from URLs using httpx with support for various file types.
    
    This tool can download files from HTTP/HTTPS URLs and save them to the local filesystem.
    It handles common file types including images, documents, archives, and more.
    """
    
    name = "download"
    description = "Download files from URLs to local filesystem. Supports various file types including images, documents, PDFs, archives, etc."
    inputs = {
        "url": {
            "type": "string", 
            "description": "URL of the file to download"
        },
        "timeout": {
            "type": "number", 
            "description": "Request timeout in seconds (optional, defaults to 30)",
            "nullable": True
        }
    }
    output_type = "string"
    
    def forward(self, url: str, timeout: float = 30.0) -> str:
        """
        Download a file from the given URL.

        Args:
            url: The URL of the file to download
            timeout: Request timeout in seconds (default: 30)
            
        Returns:
            Success message with file details or error message
        """
        # Validate URL
        if not url.startswith(('http://', 'https://')):
            return f"Error: Invalid URL format. Must start with http:// or https://"        

        try:
            with httpx.Client(timeout=timeout) as client:
                response = client.get(url, follow_redirects=True)
                response.raise_for_status()

                # Safely extract filename, fallback if URL ends with '/'
                raw_filename = url.split('/')[-1] or uuid.uuid4().hex
                file_size = len(response.content)
                content_type = response.headers.get('content-type', '')

                if 'image' in content_type:
                    # Use rsplit to only strip the last extension, not everything after first dot
                    base = raw_filename.rsplit('.', 1)[0] if '.' in raw_filename else raw_filename
                    filename = base + '.jpg'
                else:
                    filename = raw_filename

                final_save_path = os.path.join("/tmp/downloads", filename)
                os.makedirs(os.path.dirname(final_save_path), exist_ok=True)

                with open(final_save_path, 'wb') as f:
                    f.write(response.content)

                return (
                    f"✅ File downloaded successfully!\n"
                    f"• Source: {url}\n"
                    f"• Saved to: {final_save_path}\n"
                    f"• Size: {file_size} bytes\n"
                )

        except Exception as e:
            return f"Error: Unexpected error - {str(e)}"
