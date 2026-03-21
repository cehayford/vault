"""
High-level Celery monitoring and health check system.
Provides comprehensive monitoring of Celery workers, tasks, and performance metrics.
"""

import json
import time
import psutil
from datetime import datetime, timedelta
from django.conf import settings
from django.core.cache import cache
from celery import current_app
from celery.events.state import State
from celery.utils import uuid
import logging

logger = logging.getLogger(__name__)


class CeleryHealthMonitor:
    """Comprehensive Celery health monitoring system."""
    
    def __init__(self):
        self.state = State()
        self.cache_timeout = 300  # 5 minutes
        self.metrics_cache_key = 'celery_health_metrics'
        
    def get_worker_stats(self):
        """Get comprehensive worker statistics."""
        try:
            stats = current_app.control.inspect().stats()
            if not stats:
                return {'status': 'no_workers', 'workers': {}}
                
            worker_stats = {}
            total_processes = 0
            total_memory = 0
            
            for worker_name, worker_data in stats.items():
                worker_stats[worker_name] = {
                    'status': 'online',
                    'total_tasks': worker_data.get('total', 0),
                    'pool': worker_data.get('pool', {}),
                    'active_tasks': len(worker_data.get('active', [])),
                    'registered_tasks': len(worker_data.get('registered', [])),
                }
                
                # Count processes and memory if available
                if 'pool' in worker_data:
                    pool_info = worker_data['pool']
                    if 'max-concurrency' in pool_info:
                        worker_stats[worker_name]['concurrency'] = pool_info['max-concurrency']
                        total_processes += pool_info['max-concurrency']
                        
            return {
                'status': 'healthy',
                'worker_count': len(stats),
                'total_processes': total_processes,
                'workers': worker_stats
            }
        except Exception as e:
            logger.error(f"Error getting worker stats: {e}")
            return {'status': 'error', 'error': str(e)}
    
    def get_active_tasks(self):
        """Get currently active tasks."""
        try:
            active = current_app.control.inspect().active()
            if not active:
                return {'status': 'no_active_tasks', 'tasks': []}
                
            tasks = []
            for worker_name, worker_tasks in active.items():
                for task in worker_tasks:
                    tasks.append({
                        'worker': worker_name,
                        'id': task.get('id'),
                        'name': task.get('name'),
                        'args': task.get('args', []),
                        'kwargs': task.get('kwargs', {}),
                        'time_start': task.get('time_start'),
                        'duration': time.time() - task.get('time_start', time.time()) if task.get('time_start') else 0
                    })
            
            return {
                'status': 'healthy',
                'active_count': len(tasks),
                'tasks': tasks
            }
        except Exception as e:
            logger.error(f"Error getting active tasks: {e}")
            return {'status': 'error', 'error': str(e)}
    
    def get_queue_info(self):
        """Get queue information and lengths."""
        try:
            inspect = current_app.control.inspect()
            active_queues = inspect.active_queues()
            
            if not active_queues:
                return {'status': 'no_queues', 'queues': []}
            
            queue_info = []
            for worker_name, queues in active_queues.items():
                for queue in queues:
                    queue_info.append({
                        'worker': worker_name,
                        'name': queue.get('name'),
                        'exchange': queue.get('exchange'),
                        'routing_key': queue.get('routing_key'),
                        'durable': queue.get('durable', False)
                    })
            
            # Get queue lengths using Redis if available
            queue_lengths = {}
            try:
                from kombu import Connection
                redis_url = getattr(settings, 'CELERY_BROKER_URL', 'redis://localhost:6379/0')
                conn = Connection(redis_url)
                channel = conn.channel()
                
                # Common queue names to check
                queue_names = ['celery', 'email_queue', 'sms_queue', 'default']
                for queue_name in queue_names:
                    try:
                        queue_obj = channel.queue_declare(queue_name, passive=True)
                        queue_lengths[queue_name] = queue_obj.message_count
                    except:
                        queue_lengths[queue_name] = 0
                        
                conn.close()
            except Exception as e:
                logger.warning(f"Could not get queue lengths: {e}")
                queue_lengths = {q: 0 for q in ['celery', 'email_queue', 'sms_queue', 'default']}
            
            return {
                'status': 'healthy',
                'queues': queue_info,
                'lengths': queue_lengths,
                'total_pending': sum(queue_lengths.values())
            }
        except Exception as e:
            logger.error(f"Error getting queue info: {e}")
            return {'status': 'error', 'error': str(e)}
    
    def get_system_metrics(self):
        """Get system metrics relevant to Celery performance."""
        try:
            # CPU and Memory usage
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            
            # Process-specific metrics for Celery workers
            celery_processes = []
            for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent']):
                try:
                    if 'celery' in proc.info['name'].lower():
                        celery_processes.append({
                            'pid': proc.info['pid'],
                            'name': proc.info['name'],
                            'cpu_percent': proc.info['cpu_percent'],
                            'memory_percent': proc.info['memory_percent'],
                            'memory_mb': proc.info['memory_info'].rss / 1024 / 1024 if proc.info.get('memory_info') else 0
                        })
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
            
            return {
                'status': 'healthy',
                'system_cpu': cpu_percent,
                'system_memory': {
                    'total_gb': memory.total / 1024 / 1024 / 1024,
                    'available_gb': memory.available / 1024 / 1024 / 1024,
                    'percent_used': memory.percent
                },
                'celery_processes': celery_processes,
                'process_count': len(celery_processes)
            }
        except Exception as e:
            logger.error(f"Error getting system metrics: {e}")
            return {'status': 'error', 'error': str(e)}
    
    def test_task_execution(self):
        """Test task execution by sending a simple ping task."""
        try:
            # Create a simple test task
            test_task_id = str(uuid())
            
            # Send test task
            result = current_app.send_task(
                'celery_app.debug_task',
                args=[],
                kwargs={},
                task_id=test_task_id,
                expires=60  # 1 minute timeout
            )
            
            # Wait for result (with timeout)
            start_time = time.time()
            while time.time() - start_time < 10:  # 10 second timeout
                if result.ready():
                    return {
                        'status': 'healthy',
                        'execution_time': time.time() - start_time,
                        'task_id': test_task_id,
                        'success': result.successful()
                    }
                time.sleep(0.1)
            
            return {
                'status': 'timeout',
                'task_id': test_task_id,
                'timeout_seconds': 10
            }
        except Exception as e:
            logger.error(f"Error testing task execution: {e}")
            return {'status': 'error', 'error': str(e)}
    
    def get_comprehensive_health(self):
        """Get comprehensive health status of Celery system."""
        try:
            # Try to get cached metrics first
            cached_metrics = cache.get(self.metrics_cache_key)
            if cached_metrics:
                return json.loads(cached_metrics)
            
            # Collect all metrics
            health_data = {
                'timestamp': datetime.utcnow().isoformat(),
                'overall_status': 'unknown',
                'workers': self.get_worker_stats(),
                'active_tasks': self.get_active_tasks(),
                'queues': self.get_queue_info(),
                'system_metrics': self.get_system_metrics(),
                'task_execution_test': self.test_task_execution()
            }
            
            # Determine overall status
            statuses = [
                health_data['workers']['status'],
                health_data['active_tasks']['status'],
                health_data['queues']['status'],
                health_data['system_metrics']['status'],
                health_data['task_execution_test']['status']
            ]
            
            if all(status == 'healthy' for status in statuses):
                health_data['overall_status'] = 'healthy'
            elif any(status == 'error' for status in statuses):
                health_data['overall_status'] = 'error'
            else:
                health_data['overall_status'] = 'degraded'
            
            # Cache the results
            cache.set(self.metrics_cache_key, json.dumps(health_data), self.cache_timeout)
            
            return health_data
            
        except Exception as e:
            logger.error(f"Error getting comprehensive health: {e}")
            return {
                'timestamp': datetime.utcnow().isoformat(),
                'overall_status': 'error',
                'error': str(e)
            }
    
    def get_performance_metrics(self, hours=24):
        """Get performance metrics for the specified time period."""
        try:
            # This would typically query a database or log storage
            # For now, return recent performance data
            return {
                'period_hours': hours,
                'total_tasks_processed': 0,  # Would be calculated from logs
                'average_execution_time': 0,
                'success_rate': 0,
                'error_rate': 0,
                'retry_rate': 0,
                'bottlenecks': []
            }
        except Exception as e:
            logger.error(f"Error getting performance metrics: {e}")
            return {'status': 'error', 'error': str(e)}


# Singleton instance
celery_monitor = CeleryHealthMonitor()


def get_celery_health():
    """Convenience function to get Celery health."""
    return celery_monitor.get_comprehensive_health()


def is_celery_healthy():
    """Quick health check for Celery."""
    try:
        health = get_celery_health()
        return health.get('overall_status') == 'healthy'
    except:
        return False
