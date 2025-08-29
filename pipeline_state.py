#!/usr/bin/env python3
"""
Pipeline State Management Utilities
Tracks pipeline progress and enables resuming from specific stages
"""

import os
import json
import datetime
from pathlib import Path

class PipelineState:
    def __init__(self, output_dir):
        self.output_dir = Path(output_dir)
        self.state_file = self.output_dir / "pipeline_state.json"
        self.state = self._load_state()
    
    def _load_state(self):
        """Load existing state or create new one"""
        if self.state_file.exists():
            with open(self.state_file, 'r') as f:
                return json.load(f)
        else:
            return {
                'pipeline_version': '2.0-biexponential',
                'created_at': datetime.datetime.now().isoformat(),
                'stages': {
                    'preprocessing': {'status': 'pending', 'job_id': None, 'completed_at': None},
                    'dti_analysis': {'status': 'pending', 'job_id': None, 'completed_at': None},
                    'temperature_analysis': {'status': 'pending', 'job_id': None, 'completed_at': None},
                    'report_generation': {'status': 'pending', 'job_id': None, 'completed_at': None},
                    'stability_analysis': {'status': 'pending', 'job_id': None, 'completed_at': None}
                },
                'subjects': [],
                'output_files': {}
            }
    
    def save_state(self):
        """Save current state to file"""
        self.output_dir.mkdir(parents=True, exist_ok=True)
        with open(self.state_file, 'w') as f:
            json.dump(self.state, f, indent=4)
    
    def update_stage(self, stage_name, status, job_id=None, files=None):
        """Update stage status"""
        if stage_name not in self.state['stages']:
            raise ValueError(f"Unknown stage: {stage_name}")
        
        self.state['stages'][stage_name]['status'] = status
        if job_id:
            self.state['stages'][stage_name]['job_id'] = job_id
        
        if status == 'completed':
            self.state['stages'][stage_name]['completed_at'] = datetime.datetime.now().isoformat()
        
        if files:
            if stage_name not in self.state['output_files']:
                self.state['output_files'][stage_name] = []
            self.state['output_files'][stage_name].extend(files)
        
        self.save_state()
    
    def get_stage_status(self, stage_name):
        """Get status of a specific stage"""
        return self.state['stages'].get(stage_name, {}).get('status', 'unknown')
    
    def is_stage_completed(self, stage_name):
        """Check if a stage is completed"""
        return self.get_stage_status(stage_name) == 'completed'
    
    def get_next_pending_stage(self):
        """Get the next stage that needs to be run"""
        stage_order = ['preprocessing', 'dti_analysis', 'temperature_analysis', 
                      'report_generation', 'stability_analysis']
        
        for stage in stage_order:
            if self.state['stages'][stage]['status'] == 'pending':
                return stage
        return None
    
    def validate_requirements(self, stage_name, subject_id):
        """Validate that required files exist for a stage"""
        subject_dir = self.output_dir / subject_id
        
        requirements = {
            'dti_analysis': [
                'dwi_upsampled.mif',
                'dwi_mask_upsampled.mif'
            ],
            'temperature_analysis': [
                'dwi_preproc_unbiased.mif',
                'dwi_upsampled.mif', 
                'csf_norm.mif',
                'dwi_mask_upsampled.mif'
            ],
            'report_generation': [
                'temperature_map_*.mif'  # Will check with glob
            ],
            'stability_analysis': [
                'temperature_map_*.mif'  # Need at least 2
            ]
        }
        
        if stage_name not in requirements:
            return True, []
        
        missing_files = []
        for req_file in requirements[stage_name]:
            if '*' in req_file:
                # Use glob pattern
                import glob
                pattern = str(subject_dir / req_file)
                matches = glob.glob(pattern)
                if not matches:
                    missing_files.append(req_file)
                elif stage_name == 'stability_analysis' and len(matches) < 2:
                    missing_files.append(f"{req_file} (need at least 2, found {len(matches)})")
            else:
                file_path = subject_dir / req_file
                if not file_path.exists():
                    missing_files.append(req_file)
        
        return len(missing_files) == 0, missing_files
    
    def print_status(self):
        """Print current pipeline status"""
        print(f"\n=== Pipeline Status ===")
        print(f"Output Directory: {self.output_dir}")
        print(f"Created: {self.state['created_at']}")
        print(f"Version: {self.state['pipeline_version']}")
        print(f"\nStage Status:")
        
        for stage, info in self.state['stages'].items():
            status_icon = {
                'pending': '⏳',
                'running': '🔄', 
                'completed': '✅',
                'failed': '❌'
            }.get(info['status'], '❓')
            
            print(f"  {status_icon} {stage}: {info['status']}")
            if info['job_id']:
                print(f"    Job ID: {info['job_id']}")
            if info['completed_at']:
                print(f"    Completed: {info['completed_at']}")
        
        next_stage = self.get_next_pending_stage()
        if next_stage:
            print(f"\nNext stage to run: {next_stage}")
        else:
            print(f"\nAll stages completed! 🎉")


def main():
    """Command line interface for pipeline state management"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Pipeline State Management")
    parser.add_argument("output_dir", help="Pipeline output directory")
    parser.add_argument("--status", action="store_true", help="Show current status")
    parser.add_argument("--update", nargs=3, metavar=('stage', 'status', 'job_id'), 
                       help="Update stage status")
    parser.add_argument("--validate", nargs=2, metavar=('stage', 'subject_id'),
                       help="Validate requirements for stage")
    
    args = parser.parse_args()
    
    state = PipelineState(args.output_dir)
    
    if args.status:
        state.print_status()
    
    if args.update:
        stage, status, job_id = args.update
        job_id = None if job_id.lower() == 'none' else job_id
        state.update_stage(stage, status, job_id)
        print(f"Updated {stage} to {status}")
    
    if args.validate:
        stage, subject_id = args.validate
        valid, missing = state.validate_requirements(stage, subject_id)
        if valid:
            print(f"✅ All requirements met for {stage}")
        else:
            print(f"❌ Missing requirements for {stage}:")
            for file in missing:
                print(f"  - {file}")


if __name__ == "__main__":
    main()