"""
Django views for Celery monitoring and health checks.
"""

from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_http_methods
from django.contrib.admin.views.decorators import staff_member_required
from django.utils.decorators import method_decorator
from django.views.generic import TemplateView
import json
import logging

from .celery_monitor import get_celery_health, is_celery_healthy, celery_monitor

logger = logging.getLogger(__name__)


@method_decorator(staff_member_required, name='dispatch')
class CeleryHealthView(TemplateView):
    """Dashboard view for Celery health monitoring."""
    template_name = 'userauth/celery_health.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        try:
            health_data = get_celery_health()
            context.update({
                'health_data': health_data,
                'is_healthy': health_data.get('overall_status') == 'healthy',
                'last_updated': health_data.get('timestamp'),
            })
        except Exception as e:
            logger.error(f"Error loading Celery health data: {e}")
            context.update({
                'health_data': None,
                'is_healthy': False,
                'error': str(e)
            })
        return context


def celery_health_api(request):
    """API endpoint for Celery health status."""
    try:
        health_data = get_celery_health()
        
        # Format for API response
        response_data = {
            'status': health_data.get('overall_status', 'unknown'),
            'timestamp': health_data.get('timestamp'),
            'checks': {
                'workers': health_data.get('workers', {}).get('status', 'unknown'),
                'active_tasks': health_data.get('active_tasks', {}).get('status', 'unknown'),
                'queues': health_data.get('queues', {}).get('status', 'unknown'),
                'system_metrics': health_data.get('system_metrics', {}).get('status', 'unknown'),
                'task_execution': health_data.get('task_execution_test', {}).get('status', 'unknown')
            },
            'metrics': {
                'worker_count': health_data.get('workers', {}).get('worker_count', 0),
                'active_tasks': health_data.get('active_tasks', {}).get('active_count', 0),
                'pending_tasks': health_data.get('queues', {}).get('total_pending', 0),
                'system_cpu': health_data.get('system_metrics', {}).get('system_cpu', 0),
                'system_memory': health_data.get('system_metrics', {}).get('system_memory', {}),
                'test_execution_time': health_data.get('task_execution_test', {}).get('execution_time', 0)
            }
        }
        
        status_code = 200 if response_data['status'] == 'healthy' else 503
        
        return JsonResponse(response_data, status=status_code)
        
    except Exception as e:
        logger.error(f"Error in Celery health API: {e}")
        return JsonResponse({
            'status': 'error',
            'error': str(e),
            'timestamp': None
        }, status=500)


def celery_simple_health(request):
    """Simple health check endpoint for load balancers."""
    try:
        if is_celery_healthy():
            return JsonResponse({'status': 'ok', 'healthy': True}, status=200)
        else:
            return JsonResponse({'status': 'error', 'healthy': False}, status=503)
    except Exception as e:
        logger.error(f"Error in simple Celery health check: {e}")
        return JsonResponse({'status': 'error', 'healthy': False}, status=500)


@require_http_methods(["GET"])
@staff_member_required
def celery_metrics_detail(request):
    """Detailed metrics endpoint for Celery performance."""
    try:
        # Get specific metric type from query params
        metric_type = request.GET.get('type', 'all')
        hours = int(request.GET.get('hours', 24))
        
        if metric_type == 'performance':
            metrics = celery_monitor.get_performance_metrics(hours)
        elif metric_type == 'workers':
            metrics = celery_monitor.get_worker_stats()
        elif metric_type == 'tasks':
            metrics = celery_monitor.get_active_tasks()
        elif metric_type == 'queues':
            metrics = celery_monitor.get_queue_info()
        elif metric_type == 'system':
            metrics = celery_monitor.get_system_metrics()
        else:
            # All metrics
            metrics = get_celery_health()
        
        return JsonResponse({
            'status': 'success',
            'metric_type': metric_type,
            'period_hours': hours,
            'data': metrics,
            'timestamp': metrics.get('timestamp') if isinstance(metrics, dict) else None
        })
        
    except Exception as e:
        logger.error(f"Error getting Celery metrics detail: {e}")
        return JsonResponse({
            'status': 'error',
            'error': str(e)
        }, status=500)


@require_http_methods(["POST"])
@staff_member_required
def celery_test_task(request):
    """Trigger a test task to verify Celery functionality."""
    try:
        # Get test task parameters from request
        task_name = request.POST.get('task_name', 'celery_app.debug_task')
        task_args = json.loads(request.POST.get('args', '[]'))
        task_kwargs = json.loads(request.POST.get('kwargs', '{}'))
        
        # Send test task
        from celery import current_app
        result = current_app.send_task(task_name, args=task_args, kwargs=task_kwargs)
        
        return JsonResponse({
            'status': 'success',
            'task_id': result.id,
            'task_name': task_name,
            'message': f"Test task '{task_name}' sent successfully"
        })
        
    except Exception as e:
        logger.error(f"Error sending test task: {e}")
        return JsonResponse({
            'status': 'error',
            'error': str(e)
        }, status=500)


@require_http_methods(["POST"])
@staff_member_required  
def celery_clear_cache(request):
    """Clear Celery health monitoring cache."""
    try:
        from django.core.cache import cache
        cache.delete('celery_health_metrics')
        
        return JsonResponse({
            'status': 'success',
            'message': 'Celery health cache cleared successfully'
        })
        
    except Exception as e:
        logger.error(f"Error clearing Celery cache: {e}")
        return JsonResponse({
            'status': 'error',
            'error': str(e)
        }, status=500)
