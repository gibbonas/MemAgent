"""
Development Server Script for MemAgent Backend

This script provides better signal handling for Windows when running with --reload.
On Windows, uvicorn's multiprocessing reloader can hang on Ctrl+C.
This script uses watchfiles directly for better Windows compatibility.
"""

import sys
import os


if __name__ == "__main__":
    # Set environment variable to use watchfiles reloader instead of default
    os.environ["WATCHFILES_FORCE_POLLING"] = "false"
    
    try:
        # Import after setting env vars
        import uvicorn
        
        # Use reload=True but with better signal handling
        config = uvicorn.Config(
            "app.main:app",
            host="127.0.0.1",
            port=8000,
            reload=True,
            reload_dirs=["app"],
            log_level="info",
            # Use single process mode for better Windows compatibility
            workers=1,
        )
        
        server = uvicorn.Server(config)
        server.run()
        
    except KeyboardInterrupt:
        print("\n\nServer stopped.")
        sys.exit(0)
    except Exception as e:
        print(f"\n\nServer error: {e}")
        sys.exit(1)
