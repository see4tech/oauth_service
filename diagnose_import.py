# diagnose_imports.py
import sys
import importlib
import traceback

def diagnose_module_imports():
    print("Starting Comprehensive Import Diagnosis")
    
    # Ensure the project root is in Python path
    sys.path.insert(0, '/home/procesor/oauth_service')
    
    print("\nPython Path:")
    for path in sys.path:
        print(f"  {path}")
    
    print("\nImport Diagnosis:")
    try:
        # Clear any existing imports to reset state
        for key in list(sys.modules.keys()):
            if key.startswith('oauth_service'):
                del sys.modules[key]
        
        # Perform imports with detailed tracking
        print("\n--- Importing Core Modules ---")
        import oauth_service
        from oauth_service.core import get_oauth_base, get_token_manager
        from oauth_service.core.db import get_db
        
        print("\n--- Module Import Details ---")
        print("Imported modules:")
        for name, module in sys.modules.items():
            if 'oauth_service' in name:
                print(f"  {name}")
        
        # Demonstrate usage
        print("\n--- Testing Module Functionality ---")
        oauth_base = get_oauth_base()
        token_manager = get_token_manager()
        db = get_db()
        
        print("\nModules imported and instantiated successfully")
    
    except ImportError as e:
        print("Import Error:")
        print(traceback.format_exc())
    except Exception as e:
        print("Unexpected Error:")
        print(traceback.format_exc())

if __name__ == "__main__":
    diagnose_module_imports()