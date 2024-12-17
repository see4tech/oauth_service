# debug_imports.py
import sys
import importlib
import os
import traceback

def debug_imports():
    print("Python Executable:", sys.executable)
    print("Current Working Directory:", os.getcwd())
    print("Python Version:", sys.version)
    
    print("\nPython Path:")
    for path in sys.path:
        print(f"  {path}")
    
    print("\nEnvironment Variables:")
    print("  PYTHONPATH:", os.environ.get('PYTHONPATH', 'Not set'))
    
    print("\nAll Imported Modules:")
    try:
        # Try to import the oauth_service package
        import oauth_service
        
        print("\nOAuth Service Package Details:")
        print(f"Package Location: {oauth_service.__file__}")
        
        # List all oauth_service related modules
        print("\nOAuth Service Modules:")
        for name, module in sorted(sys.modules.items()):
            if 'oauth_service' in str(name):
                try:
                    print(f"Module: {name}")
                    print(f"  File: {module.__file__}")
                except AttributeError:
                    print(f"  Module {name} has no __file__ attribute")
                print("---")
    
    except ImportError as e:
        print("Error importing oauth_service:")
        print(traceback.format_exc())
    
    print("\nFull Module List:")
    for name in sorted(sys.modules.keys()):
        print(name)

if __name__ == "__main__":
    debug_imports()