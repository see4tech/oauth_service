# debug_imports.py
import sys
import importlib
import os

def debug_imports():
    print("Python Path:", sys.path)
    print("\nAll Imported Modules:")
    for name, module in sorted(sys.modules.items()):
        if 'oauth_service' in str(name):
            print(f"Module: {name}")
            try:
                print(f"File: {module.__file__}")
            except AttributeError:
                print("No file attribute")
            print("---")

if __name__ == "__main__":
    debug_imports()