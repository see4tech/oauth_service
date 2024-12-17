# debug_project.py
import os
import sys
import importlib

def list_project_files(base_path):
    print("Project File Structure:")
    for root, dirs, files in os.walk(base_path):
        level = root.replace(base_path, '').count(os.sep)
        indent = ' ' * 4 * level
        print(f"{indent}{os.path.basename(root)}/")
        subindent = ' ' * 4 * (level + 1)
        for file in files:
            print(f"{subindent}{file}")

def check_imports(package_name):
    print(f"\nChecking imports for {package_name}:")
    try:
        package = importlib.import_module(package_name)
        print(f"Package Location: {package.__file__}")
        
        # Recursively check submodules
        def check_submodules(package_name):
            try:
                package = importlib.import_module(package_name)
                for name in dir(package):
                    if not name.startswith('_'):
                        try:
                            submodule = getattr(package, name)
                            if hasattr(submodule, '__file__'):
                                print(f"  Submodule: {package_name}.{name}")
                                print(f"    Location: {submodule.__file__}")
                        except ImportError:
                            pass
            except ImportError:
                print(f"Could not import {package_name}")
        
        check_submodules(package_name)
    
    except ImportError as e:
        print(f"Error importing {package_name}:")
        print(e)

def main():
    base_path = "/home/procesor/oauth_service"
    project_path = os.path.join(base_path, "oauth_service")
    
    # Add project to Python path
    sys.path.insert(0, base_path)
    
    # List project files
    list_project_files(project_path)
    
    # Check imports
    check_imports("oauth_service")

if __name__ == "__main__":
    main()