# diagnose_import.py
import sys
import importlib
import traceback

def diagnose_module_import():
    print("Starting Module Import Diagnosis")
    
    # Ensure the project root is in Python path
    sys.path.insert(0, '/home/procesor/oauth_service')
    
    print("\nPython Path:")
    for path in sys.path:
        print(f"  {path}")
    
    print("\nImport Diagnosis:")
    try:
        # Explicitly reload the module to reset any previous state
        if 'oauth_service.core.db' in sys.modules:
            del sys.modules['oauth_service.core.db']
        
        # Perform the import
        import oauth_service.core.db as db_module
        
        print("\nModule Import Details:")
        print(f"Module: {db_module}")
        print(f"Module File: {db_module.__file__}")
        
        # Demonstrate database access
        print("\nTesting Database Access:")
        db_instance = db_module.get_db()
        print("Database instance retrieved successfully")
        
        # Print module loading context
        print("\nModule Loading Context:")
        print("Modules in sys.modules:")
        for name, module in sys.modules.items():
            if 'oauth_service' in str(name):
                print(f"  {name}")
    
    except ImportError as e:
        print("Import Error:")
        print(traceback.format_exc())
    except Exception as e:
        print("Unexpected Error:")
        print(traceback.format_exc())

if __name__ == "__main__":
    diagnose_module_import()