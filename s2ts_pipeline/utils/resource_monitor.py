import psutil
import time
import threading
from typing import Dict, Any
import pynvml  # For GPU monitoring

class ResourceMonitor:
    """Monitor system resources including CPU, RAM, GPU, and Disk."""
    
    def __init__(self):
        self.stats = {
            'cpu': 0,
            'memory': 0,
            'gpu': 0,
            'gpu_memory': 0,
            'disk': 0
        }
        self._stop_event = threading.Event()
        self._monitor_thread = None
        self._gpu_available = False
        
        # Initialize GPU monitoring if available
        try:
            pynvml.nvmlInit()
            self._gpu_available = True
            self._gpu_handle = pynvml.nvmlDeviceGetHandleByIndex(0)
        except Exception:
            self._gpu_available = False
    
    def update_stats(self) -> None:
        """Update resource statistics."""
        # CPU usage
        self.stats['cpu'] = psutil.cpu_percent()
        
        # Memory usage
        memory = psutil.virtual_memory()
        self.stats['memory'] = memory.percent
        
        # Disk usage
        disk = psutil.disk_usage('/')
        self.stats['disk'] = disk.percent
        
        # GPU usage
        if self._gpu_available:
            try:
                utilization = pynvml.nvmlDeviceGetUtilizationRates(self._gpu_handle)
                memory_info = pynvml.nvmlDeviceGetMemoryInfo(self._gpu_handle)
                self.stats['gpu'] = utilization.gpu
                self.stats['gpu_memory'] = (memory_info.used / memory_info.total) * 100
            except Exception:
                self.stats['gpu'] = 0
                self.stats['gpu_memory'] = 0
        else:
            self.stats['gpu'] = 0
            self.stats['gpu_memory'] = 0
    
    def get_stats(self) -> Dict[str, float]:
        """Get current resource statistics."""
        return self.stats
    
    def start_monitoring(self, interval: int = 5) -> None:
        """Start background monitoring."""
        if self._monitor_thread and self._monitor_thread.is_alive():
            return
            
        self._stop_event.clear()
        self._monitor_thread = threading.Thread(
            target=self._monitor_loop, 
            args=(interval,),
            daemon=True
        )
        self._monitor_thread.start()
    
    def stop_monitoring(self) -> None:
        """Stop background monitoring."""
        self._stop_event.set()
        if self._monitor_thread:
            self._monitor_thread.join(timeout=2.0)
    
    def _monitor_loop(self, interval: int) -> None:
        """Background monitoring loop."""
        while not self._stop_event.is_set():
            self.update_stats()
            time.sleep(interval)
    
    def __del__(self):
        """Cleanup when object is destroyed."""
        self.stop_monitoring()
        if self._gpu_available:
            try:
                pynvml.nvmlShutdown()
            except:
                pass