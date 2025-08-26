import time
from typing import Dict, Any
from datetime import datetime

class StageProgress:
    """Track progress of each pipeline stage."""
    
    def __init__(self):
        self.stages = {
            'asr': {'progress': 0, 'status': 'pending', 'time_taken': 0, 'start_time': None},
            'clean': {'progress': 0, 'status': 'pending', 'time_taken': 0, 'start_time': None},
            'translate': {'progress': 0, 'status': 'pending', 'time_taken': 0, 'start_time': None},
            'tts': {'progress': 0, 'status': 'pending', 'time_taken': 0, 'start_time': None}
        }
    
    def start_stage(self, stage_name: str) -> None:
        """Mark a stage as started."""
        if stage_name not in self.stages:
            self.stages[stage_name] = {'progress': 0, 'status': 'running', 'time_taken': 0}
        
        self.stages[stage_name]['status'] = 'running'
        self.stages[stage_name]['progress'] = 0
        self.stages[stage_name]['start_time'] = time.time()
    
    def update_stage(self, stage_name: str, progress: int) -> None:
        """Update progress for a stage."""
        if stage_name in self.stages:
            self.stages[stage_name]['progress'] = progress
    
    def complete_stage(self, stage_name: str, time_taken: float = None) -> None:
        """Mark a stage as completed."""
        if stage_name in self.stages:
            if time_taken is None and self.stages[stage_name]['start_time']:
                time_taken = time.time() - self.stages[stage_name]['start_time']
            
            self.stages[stage_name]['status'] = 'completed'
            self.stages[stage_name]['progress'] = 100
            self.stages[stage_name]['time_taken'] = time_taken or 0
    
    def fail_stage(self, stage_name: str, error_message: str) -> None:
        """Mark a stage as failed."""
        if stage_name in self.stages:
            self.stages[stage_name]['status'] = 'failed'
            self.stages[stage_name]['error'] = error_message
    
    def get_progress(self) -> Dict[str, Any]:
        """Get current progress for all stages."""
        return self.stages
    
    def get_stage_progress(self, stage_name: str) -> Dict[str, Any]:
        """Get progress for a specific stage."""
        return self.stages.get(stage_name, {'progress': 0, 'status': 'pending'})
    
    def reset(self) -> None:
        """Reset all progress tracking."""
        for stage in self.stages:
            self.stages[stage] = {'progress': 0, 'status': 'pending', 'time_taken': 0, 'start_time': None}