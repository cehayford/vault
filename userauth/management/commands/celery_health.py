"""
Django management command to check Celery health and performance.
"""

from django.core.management.base import BaseCommand
from django.utils import timezone
import json

from userauth.celery_monitor import get_celery_health, is_celery_healthy
from userauth.celery_analytics import get_celery_performance_metrics, get_celery_error_trends
from userauth.celery_alerts import check_celery_health_alerts


class Command(BaseCommand):
    help = 'Check Celery health and performance metrics'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--json',
            action='store_true',
            help='Output results in JSON format'
        )
        parser.add_argument(
            '--quick',
            action='store_true',
            help='Quick health check only'
        )
        parser.add_argument(
            '--alerts',
            action='store_true',
            help='Run health alert checks'
        )
        parser.add_argument(
            '--hours',
            type=int,
            default=24,
            help='Hours of data to analyze (default: 24)'
        )
    
    def handle(self, *args, **options):
        if options['alerts']:
            self.stdout.write("Running Celery health alert checks...")
            check_celery_health_alerts()
            self.stdout.write(self.style.SUCCESS("✅ Health alert checks completed"))
            return
        
        if options['quick']:
            # Quick health check
            is_healthy = is_celery_healthy()
            if is_healthy:
                self.stdout.write(self.style.SUCCESS("✅ Celery is healthy"))
                exit_code = 0
            else:
                self.stdout.write(self.style.ERROR("❌ Celery is unhealthy"))
                exit_code = 1
        else:
            # Comprehensive health check
            self.stdout.write("Checking Celery health and performance...")
            
            # Get health data
            health_data = get_celery_health()
            hours = options['hours']
            
            if options['json']:
                output = {
                    'timestamp': timezone.now().isoformat(),
                    'health': health_data,
                    'performance': get_celery_performance_metrics(hours),
                    'error_trends': get_celery_error_trends(hours)
                }
                self.stdout.write(json.dumps(output, indent=2))
            else:
                self._print_human_readable_output(health_data, hours)
        
        # Set exit code based on overall status
        if health_data.get('overall_status') != 'healthy':
            exit(1)
    
    def _print_human_readable_output(self, health_data, hours):
        """Print human-readable health report."""
        overall_status = health_data.get('overall_status', 'unknown')
        
        # Status with color
        if overall_status == 'healthy':
            status_icon = "✅"
            status_color = self.style.SUCCESS
        elif overall_status == 'degraded':
            status_icon = "⚠️"
            status_color = self.style.WARNING
        else:
            status_icon = "❌"
            status_color = self.style.ERROR
        
        # Header
        self.stdout.write("\n" + "="*60)
        self.stdout.write(f"📊 CELERY HEALTH REPORT - {timezone.now().strftime('%Y-%m-%d %H:%M:%S')}")
        self.stdout.write("="*60)
        
        # Overall Status
        self.stdout.write(f"\n{status_icon} OVERALL STATUS: {status_color(overall_status.upper())}")
        self.stdout.write(f"   Last Check: {health_data.get('timestamp', 'Unknown')}")
        
        # Component Statuses
        self.stdout.write(f"\n📋 COMPONENT STATUS:")
        
        workers = health_data.get('workers', {})
        self.stdout.write(f"   Workers: {self._get_status_icon(workers.get('status'))} {workers.get('status', 'unknown').upper()}")
        if workers.get('worker_count'):
            self.stdout.write(f"   Count: {workers.get('worker_count')} workers, {workers.get('total_processes')} processes")
        
        active_tasks = health_data.get('active_tasks', {})
        self.stdout.write(f"   Active Tasks: {self._get_status_icon(active_tasks.get('status'))} {active_tasks.get('status', 'unknown').upper()}")
        if active_tasks.get('active_count'):
            self.stdout.write(f"   Count: {active_tasks.get('active_count')} tasks running")
        
        queues = health_data.get('queues', {})
        self.stdout.write(f"   Queues: {self._get_status_icon(queues.get('status'))} {queues.get('status', 'unknown').upper()}")
        if queues.get('total_pending') is not None:
            self.stdout.write(f"   Pending: {queues.get('total_pending')} tasks")
        
        system = health_data.get('system_metrics', {})
        self.stdout.write(f"   System: {self._get_status_icon(system.get('status'))} {system.get('status', 'unknown').upper()}")
        if system.get('system_cpu') is not None:
            self.stdout.write(f"   CPU: {system.get('system_cpu', 0):.1f}%")
        if system.get('system_memory', {}).get('percent_used') is not None:
            self.stdout.write(f"   Memory: {system.get('system_memory', {}).get('percent_used', 0):.1f}%")
        
        task_test = health_data.get('task_execution_test', {})
        self.stdout.write(f"   Task Test: {self._get_status_icon(task_test.get('status'))} {task_test.get('status', 'unknown').upper()}")
        if task_test.get('execution_time') is not None:
            self.stdout.write(f"   Exec Time: {task_test.get('execution_time', 0):.2f}s")
        
        # Performance Summary
        perf_metrics = get_celery_performance_metrics(hours)
        if 'error' not in perf_metrics:
            summary = perf_metrics.get('summary', {})
            self.stdout.write(f"\n📈 PERFORMANCE SUMMARY (last {hours}h):")
            self.stdout.write(f"   Total Tasks: {summary.get('total_tasks', 0)}")
            self.stdout.write(f"   Success Rate: {summary.get('success_rate', 0):.1f}%")
            self.stdout.write(f"   Avg Duration: {summary.get('average_duration', 0):.2f}s")
        
        # Recent Issues
        error_trends = get_celery_error_trends(hours)
        if 'error' not in error_trends:
            recent_failures = error_trends.get('recent_failures', [])[:5]
            if recent_failures:
                self.stdout.write(f"\n⚠️  RECENT ISSUES:")
                for failure in recent_failures:
                    task_name = failure.get('task_name', 'Unknown')[:30]
                    error_type = failure.get('exception_type', 'Unknown')[:20]
                    self.stdout.write(f"   • {task_name}: {error_type}")
        
        self.stdout.write("\n" + "="*60)
    
    def _get_status_icon(self, status):
        """Get colored status icon."""
        if status == 'healthy':
            return "✅"
        elif status == 'degraded':
            return "⚠️"
        elif status == 'error':
            return "❌"
        else:
            return "❓"
