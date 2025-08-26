import json
import os
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime

class StateManager:
    """Manage pipeline state and caching with JSON persistence."""
    
    def __init__(self, state_file: str = "pipeline_state.json"):
        self.state_file = Path(state_file)
        self.state = self._load_state()
    
    def _load_state(self) -> Dict[str, Any]:
        """Load state from file."""
        if self.state_file.exists():
            try:
                with open(self.state_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception:
                return {}
        return {}
    
    def save_state(self) -> None:
        """Save current state to file."""
        with open(self.state_file, 'w', encoding='utf-8') as f:
            json.dump(self.state, f, indent=2, ensure_ascii=False)
    
    def get_cached_result(self, stage_name: str, cache_key: str) -> Optional[Any]:
        """Get cached result for a stage if available."""
        cache = self.state.get('cache', {})
        return cache.get(f"{stage_name}_{cache_key}", None)
    
    def cache_result(self, stage_name: str, cache_key: str, result: Any) -> None:
        """Cache a stage result."""
        if 'cache' not in self.state:
            self.state['cache'] = {}
        
        self.state['cache'][f"{stage_name}_{cache_key}"] = {
            "result": result,
            "timestamp": datetime.now().isoformat()
        }
        self.save_state()
    
    def update_stage_status(self, stage_name: str, status: str, 
                          details: Optional[Dict[str, Any]] = None) -> None:
        """Update the status of a pipeline stage."""
        if 'stages' not in self.state:
            self.state['stages'] = {}
        
        self.state['stages'][stage_name] = {
            "status": status,
            "last_updated": datetime.now().isoformat(),
            "details": details or {}
        }
        self.save_state()
    
    def get_stage_status(self, stage_name: str) -> Dict[str, Any]:
        """Get the current status of a pipeline stage."""
        return self.state.get('stages', {}).get(stage_name, {"status": "pending"})