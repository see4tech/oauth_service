# debug_db_import.py
import sys
import importlib
import traceback

def debug_db_import():
    print("Starting DB Import Debug")
    
    # Ensure the project root is in Python path
    sys.path.insert(0, '/home/procesor/oauth_service')
    
    print("\nPython Path:")
    for path in sys.path:
        print(f"  {path}")
    
    print("\nAttempting to import oauth_service.core.db")
    try:
        # Use importlib for more controlled import
        import oauth_service.core.db as db_module
        
        print("\nModule Import Details:")
        print(f"Module: {db_module}")
        print(f"Module File: {db_module.__file__}")
        
        # Demonstrate database usage
        print("\nTesting Database Access:")
        db_instance = db_module.get_db()
        print("Database instance retrieved successfully")
        
    except ImportError as e:
        print("Import Error:")
        print(traceback.format_exc())
    except Exception as e:
        print("Unexpected Error:")
        print(traceback.format_exc())

if __name__ == "__main__":
    debug_db_import()