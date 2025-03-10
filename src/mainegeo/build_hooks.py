from pathlib import Path
import importlib.util
import sys

def build_hook(directory):
    """Run preprocessing during wheel build"""
    # Dynamically import the build module
    build_path = Path(directory) / "mainegeo" / "build.py"
    spec = importlib.util.spec_from_file_location("build", build_path)
    build_module = importlib.util.module_from_spec(spec)
    sys.modules["build"] = build_module
    spec.loader.exec_module(build_module)
    
    # Execute the build function
    build_module.build_town_database()
    
    # Make sure the YAML file is included in the wheel
    return {
        "include": ["mainegeo/data/townships.yaml"]
    }