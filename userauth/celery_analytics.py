"""
Celery task performance analytics and monitoring system.
Tracks task execution times, success rates, and performance trends.
"""

import json
import time
from datetime import datetime, timedelta
from django.conf import settings
from django.core.cache import cache
from django.db import models
from celery import current_app
import logging

logger = logging.getLogger(__name__)


class CeleryTaskMetrics(models.Model):
    """Model to store Celery task performance metrics."""
    
    task_name = models.CharField(max_length=255, db_index=True)
    task_id = models.CharField(max_length=255, unique=True, db_index=True)
    worker_name = models.CharField(max_length=255, db_index=True)
    
    # Timing information
    started_at = models.DateTimeField(db_index=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    duration_seconds = models.FloatField(null=True, blank=True)
    
    # Status information
    status = models.CharField(
        max_length=20,
        choices=[
            ('PENDING', 'Pending'),
            ('STARTED', 'Started'),
            ('SUCCESS', 'Success'),
            ('FAILURE', 'Failure'),
            ('RETRY', 'Retry'),
            ('REVOKED', 'Revoked'),
        ],
        db_index=True
    )
    
    # Error information
    exception_type = models.CharField(max_length=255, null=True, blank=True)
    exception_message = models.TextField(null=True, blank=True)
    traceback = models.TextField(null=True, blank=True)
    
    # Retry information
    retry_count = models.PositiveIntegerField(default=0)
    max_retries = models.PositiveIntegerField(default=3)
    
    # Queue information
    queue_name = models.CharField(max_length=255, db_index=True)
    
    # Additional metadata
    args_json = models.TextField(null=True, blank=True)
    kwargs_json = models.TextField(null=True, blank=True)
    result_json = models.TextField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    
    class Meta:
        app_label = 'userauth'
        db_table = 'celery_task_metrics'
        indexes = [
            models.Index(fields=['task_name', 'created_at']),
            models.Index(fields=['status', 'created_at']),
            models.Index(fields=['worker_name', 'created_at']),
            models.Index(fields=['queue_name', 'created_at']),
        ]
    
    def __str__(self):
        return f"{self.task_name} - {self.task_id[:8]}... ({self.status})"
    
    @property
    def args(self):
        if self.args_json:
            try:
                return json.loads(self.args_json)
            except:
                return []
        return []
    
    @property
    def kwargs(self):
        if self.kwargs_json:
            try:
                return json.loads(self.kwargs_json)
            except:
                return {}
        return {}
    
    @property
    def result(self):
        if self.result_json:
            try:
                return json.loads(self.result_json)
            except:
                return None
        return None


class CeleryPerformanceAnalyzer:
    """High-level performance analysis for Celery tasks."""
    
    def __init__(self):
        self.cache_timeout = 300  # 5 minutes
        
    def record_task_start(self, task_id, task_name, worker_name, queue_name='default', args=None, kwargs=None):
        """Record the start of a task execution."""
        try:
            CeleryTaskMetrics.objects.update_or_create(
                task_id=task_id,
                defaults={
                    'task_name': task_name,
                    'worker_name': worker_name,
                    'queue_name': queue_name,
                    'started_at': datetime.utcnow(),
                    'status': 'STARTED',
                    'args_json': json.dumps(args) if args else None,
                    'kwargs_json': json.dumps(kwargs) if kwargs else None,
                }
            )
        except Exception as e:
            logger.error(f"Error recording task start: {e}")
    
    def record_task_completion(self, task_id, status='SUCCESS', result=None, exception=None, traceback=None):
        """Record the completion of a task execution."""
        try:
            metrics = CeleryTaskMetrics.objects.filter(task_id=task_id).first()
            if metrics:
                metrics.completed_at = datetime.utcnow()
                metrics.status = status
                metrics.result_json = json.dumps(result) if result else None
                
                if exception:
                    metrics.exception_type = exception.__class__.__name__ if hasattr(exception, '__class__') else str(exception)
                    metrics.exception_message = str(exception)
                    metrics.traceback = traceback
                
                if metrics.started_at:
                    metrics.duration_seconds = (metrics.completed_at - metrics.started_at).total_seconds()
                
                metrics.save()
        except Exception as e:
            logger.error(f"Error recording task completion: {e}")
    
    def get_performance_summary(self, hours=24):
        """Get performance summary for the specified time period."""
        try:
            since = datetime.utcnow() - timedelta(hours=hours)
            
            # Basic metrics
            total_tasks = CeleryTaskMetrics.objects.filter(created_at__gte=since).count()
            successful_tasks = CeleryTaskMetrics.objects.filter(
                created_at__gte=since, 
                status='SUCCESS'
            ).count()
            failed_tasks = CeleryTaskMetrics.objects.filter(
                created_at__gte=since, 
                status='FAILURE'
            ).count()
            
            # Calculate rates
            success_rate = (successful_tasks / total_tasks * 100) if total_tasks > 0 else 0
            failure_rate = (failed_tasks / total_tasks * 100) if total_tasks > 0 else 0
            
            # Performance metrics
            completed_tasks = CeleryTaskMetrics.objects.filter(
                created_at__gte=since,
                status='SUCCESS',
                duration_seconds__isnull=False
            )
            
            avg_duration = 0
            if completed_tasks.exists():
                total_duration = completed_tasks.aggregate(
                    total=models.Sum('duration_seconds')
                )['total'] or 0
                avg_duration = total_duration / completed_tasks.count()
            
            # Task breakdown
            task_breakdown = CeleryTaskMetrics.objects.filter(
                created_at__gte=since
            ).values('task_name').annotate(
                count=models.Count('id'),
                success_count=models.Count('id', filter=models.Q(status='SUCCESS')),
                failure_count=models.Count('id', filter=models.Q(status='FAILURE')),
                avg_duration=models.Avg('duration_seconds')
            ).order_by('-count')[:10]  # Top 10 tasks
            
            # Worker breakdown
            worker_breakdown = CeleryTaskMetrics.objects.filter(
                created_at__gte=since
            ).values('worker_name').annotate(
                count=models.Count('id'),
                success_count=models.Count('id', filter=models.Q(status='SUCCESS')),
                failure_count=models.Count('id', filter=models.Q(status='FAILURE')),
                avg_duration=models.Avg('duration_seconds')
            ).order_by('-count')
            
            # Queue breakdown
            queue_breakdown = CeleryTaskMetrics.objects.filter(
                created_at__gte=since
            ).values('queue_name').annotate(
                count=models.Count('id'),
                pending_count=models.Count('id', filter=models.Q(status='PENDING')),
                success_count=models.Count('id', filter=models.Q(status='SUCCESS')),
                failure_count=models.Count('id', filter=models.Q(status='FAILURE'))
            ).order_by('-count')
            
            return {
                'period_hours': hours,
                'summary': {
                    'total_tasks': total_tasks,
                    'successful_tasks': successful_tasks,
                    'failed_tasks': failed_tasks,
                    'success_rate': round(success_rate, 2),
                    'failure_rate': round(failure_rate, 2),
                    'average_duration': round(avg_duration, 3),
                },
                'task_breakdown': list(task_breakdown),
                'worker_breakdown': list(worker_breakdown),
                'queue_breakdown': list(queue_breakdown),
                'generated_at': datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error generating performance summary: {e}")
            return {'error': str(e)}
    
    def get_slow_tasks(self, hours=24, limit=10):
        """Get the slowest tasks in the specified time period."""
        try:
            since = datetime.utcnow() - timedelta(hours=hours)
            
            slow_tasks = CeleryTaskMetrics.objects.filter(
                created_at__gte=since,
                status='SUCCESS',
                duration_seconds__isnull=False
            ).order_by('-duration_seconds')[:limit]
            
            return list(slow_tasks.values(
                'task_name',
                'task_id',
                'duration_seconds',
                'worker_name',
                'completed_at'
            ))
            
        except Exception as e:
            logger.error(f"Error getting slow tasks: {e}")
            return []
    
    def get_error_trends(self, hours=24):
        """Get error trends and common failure patterns."""
        try:
            since = datetime.utcnow() - timedelta(hours=hours)
            
            # Recent failures
            recent_failures = CeleryTaskMetrics.objects.filter(
                created_at__gte=since,
                status='FAILURE'
            ).order_by('-created_at')[:20]
            
            # Error types breakdown
            error_types = CeleryTaskMetrics.objects.filter(
                created_at__gte=since,
                status='FAILURE',
                exception_type__isnull=False
            ).values('exception_type').annotate(
                count=models.Count('id')
            ).order_by('-count')
            
            # Tasks with highest failure rates
            task_failure_rates = CeleryTaskMetrics.objects.filter(
                created_at__gte=since
            ).values('task_name').annotate(
                total=models.Count('id'),
                failures=models.Count('id', filter=models.Q(status='FAILURE'))
            ).annotate(
                failure_rate=models.F('failures') * 100.0 / models.F('total')
            ).filter(total__gte=5).order_by('-failure_rate')[:10]
            
            return {
                'period_hours': hours,
                'recent_failures': list(recent_failures.values(
                    'task_name',
                    'exception_type',
                    'exception_message',
                    'worker_name',
                    'created_at'
                )),
                'error_types': list(error_types),
                'high_failure_tasks': list(task_failure_rates),
                'generated_at': datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error getting error trends: {e}")
            return {'error': str(e)}
    
    def get_queue_health(self):
        """Get detailed queue health information."""
        try:
            # Queue metrics
            queue_metrics = CeleryTaskMetrics.objects.filter(
                created_at__gte=datetime.utcnow() - timedelta(hours=1)
            ).values('queue_name').annotate(
                pending=models.Count('id', filter=models.Q(status='PENDING')),
                processing=models.Count('id', filter=models.Q(status='STARTED')),
                completed=models.Count('id', filter=models.Q(status='SUCCESS')),
                failed=models.Count('id', filter=models.Q(status='FAILURE'))
            ).order_by('-pending')
            
            return {
                'queue_metrics': list(queue_metrics),
                'total_queues': queue_metrics.count(),
                'generated_at': datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error getting queue health: {e}")
            return {'error': str(e)}


# Singleton instance
performance_analyzer = CeleryPerformanceAnalyzer()


def get_celery_performance_metrics(hours=24):
    """Convenience function to get performance metrics."""
    return performance_analyzer.get_performance_summary(hours)


def get_celery_error_trends(hours=24):
    """Convenience function to get error trends."""
    return performance_analyzer.get_error_trends(hours)
