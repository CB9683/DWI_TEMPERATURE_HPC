#!/usr/bin/env python3
"""
Get the latest pipeline output directory
This helper script finds the most recently created pipeline output directory
"""
import os, json, glob, sys
from datetime import datetime

def get_latest_output_dir():
    """Find the most recent pipeline output directory"""
    
    # Load configuration to get base output path
    config_file = "pipeline_config.json"
    if not os.path.exists(config_file):
        print(f"ERROR: Configuration file {config_file} not found!", file=sys.stderr)
        sys.exit(1)
    
    with open(config_file, 'r') as f:
        config = json.load(f)
    
    base_output = config['paths']['base_output']
    
    # Look for directories matching temp_pipeline_* pattern
    pattern = os.path.join(base_output, 'temp_pipeline_*')
    directories = glob.glob(pattern)
    
    if not directories:
        print(f"ERROR: No pipeline output directories found in {base_output}", file=sys.stderr)
        print("Have you run preprocessing yet?", file=sys.stderr)
        sys.exit(1)
    
    # Sort by modification time (most recent first)
    directories.sort(key=os.path.getmtime, reverse=True)
    latest_dir = directories[0]
    
    return latest_dir

def main():
    if len(sys.argv) > 1:
        if sys.argv[1] == '--help' or sys.argv[1] == '-h':
            print("Usage: python3 get_latest_output.py")
            print("Returns the path to the most recent pipeline output directory")
            return
        elif sys.argv[1] == '--list':
            # List all pipeline directories
            config_file = "pipeline_config.json"
            with open(config_file, 'r') as f:
                config = json.load(f)
            base_output = config['paths']['base_output']
            pattern = os.path.join(base_output, 'temp_pipeline_*')
            directories = glob.glob(pattern)
            directories.sort(key=os.path.getmtime, reverse=True)
            
            if not directories:
                print("No pipeline output directories found.")
                return
            
            print("Available pipeline output directories (newest first):")
            for i, d in enumerate(directories):
                mtime = os.path.getmtime(d)
                date_str = datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M:%S")
                print(f"  {i+1}. {d} ({date_str})")
            return
    
    # Default: return latest directory path
    latest_dir = get_latest_output_dir()
    print(latest_dir)

if __name__ == "__main__":
    main()