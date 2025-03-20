#!/usr/bin/env python3
"""
Build script that:
1. Checks if Node.js is available (for development only)
2. Builds the frontend if in development
3. Ensures the static directory exists with frontend files
"""
import os
import shutil
import subprocess
import sys
from pathlib import Path

def check_node():
    """Check if Node.js is available."""
    try:
        subprocess.run(['node', '--version'], capture_output=True, check=True)
        return True
    except (subprocess.SubprocessError, FileNotFoundError):
        return False

def build_frontend():
    """Build the frontend using npm."""
    frontend_dir = Path('frontend')
    if not frontend_dir.exists():
        print("No frontend directory found, skipping build")
        return False
    
    if not check_node():
        print("Node.js not found, skipping frontend build")
        return False
    
    print("Building frontend...")
    try:
        # Install dependencies
        subprocess.run(['npm', 'install'], cwd=frontend_dir, check=True)
        # Build the project
        subprocess.run(['npm', 'run', 'build'], cwd=frontend_dir, check=True)
        return True
    except subprocess.SubprocessError as e:
        print(f"Error building frontend: {e}")
        return False

def copy_static_files():
    """Copy built frontend files to the static directory."""
    frontend_build = Path('frontend/dist')
    static_dir = Path('src/mcp_gateway/static')
    
    # Create static directory if it doesn't exist
    static_dir.mkdir(parents=True, exist_ok=True)
    
    if frontend_build.exists():
        # Copy built files
        for item in frontend_build.glob('*'):
            if item.is_file():
                shutil.copy2(item, static_dir)
            else:
                dest = static_dir / item.name
                if dest.exists():
                    shutil.rmtree(dest)
                shutil.copytree(item, dest)
        print("Copied built frontend files to static directory")
    else:
        # Ensure we at least have a basic index.html
        index_path = static_dir / 'index.html'
        if not index_path.exists():
            with open(index_path, 'w') as f:
                f.write("""<!DOCTYPE html>
<html>
<head>
    <title>MCP Gateway</title>
</head>
<body>
    <h1>MCP Gateway</h1>
    <p>Frontend not built. Run with Node.js available for full interface.</p>
</body>
</html>""")
            print("Created basic index.html in static directory")

def main():
    """Main build script."""
    os.chdir(Path(__file__).parent.parent)  # Change to project root
    build_frontend()
    copy_static_files()

if __name__ == '__main__':
    main() 