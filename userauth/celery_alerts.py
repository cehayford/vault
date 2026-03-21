"""
Automated health alert system for Celery monitoring.
Sends notifications when Celery health issues are detected.
"""

import time
from datetime import datetime, timedelta
from django.conf import settings
from django.core.mail import send_mail
from django.core.cache import cache
import logging

from .celery_monitor import get_celery_health, is_celery_healthy
from .celery_analytics import get_celery_performance_metrics, get_celery_error_trends

logger = logging.getLogger(__name__)


class CeleryHealthAlerts:
    """Automated alert system for Celery health monitoring."""
    
    def __init__(self):
        self.alert_cache_key = 'celery_health_alerts'
        self.alert_cooldown = 300  # 5 minutes between same alert type
        self.email_recipients = getattr(settings, 'CELERY_ALERT_EMAILS', [])
        
    def should_send_alert(self, alert_type):
        """Check if alert should be sent (cooldown logic)."""
        cache_key = f"{self.alert_cache_key}_{alert_type}"
        last_sent = cache.get(cache_key)
        
        if last_sent:
            return False
        
        # Set cooldown
        cache.set(cache_key, datetime.utcnow().isoformat(), self.alert_cooldown)
        return True
    
    def send_alert(self, subject, message, alert_type='general'):
        """Send health alert via email and log."""
        if not self.should_send_alert(alert_type):
            return
        
        try:
            # Log the alert
            logger.warning(f"Celery Health Alert [{alert_type}]: {subject}")
            
            # Send email if recipients are configured
            if self.email_recipients:
                send_mail(
                    subject=subject,
                    message=message,
                    from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@vault.local'),
                    recipient_list=self.email_recipients,
                    fail_silently=False,
                )
                logger.info(f"Alert email sent to {len(self.email_recipients)} recipients")
            
        except Exception as e:
            logger.error(f"Failed to send Celery health alert: {e}")
    
    def check_and_alert(self):
        """Perform comprehensive health checks and send alerts if needed."""
        try:
            health_data = get_celery_health()
            overall_status = health_data.get('overall_status', 'unknown')
            
            # Check overall system health
            if overall_status == 'error':
                self.send_alert(
                    subject="🚨 CELERY SYSTEM ERROR",
                    message=f"""
Celery system is in ERROR state.

System Status: {overall_status.upper()}
Timestamp: {health_data.get('timestamp')}

Component Statuses:
- Workers: {health_data.get('workers', {}).get('status', 'unknown')}
- Active Tasks: {health_data.get('active_tasks', {}).get('status', 'unknown')}
- Queues: {health_data.get('queues', {}).get('status', 'unknown')}
- System Metrics: {health_data.get('system_metrics', {}).get('status', 'unknown')}
- Task Execution: {health_data.get('task_execution_test', {}).get('status', 'unknown')}

Please check the Celery monitoring dashboard for details.
                    """.strip(),
                    alert_type='system_error'
                )
            
            elif overall_status == 'degraded':
                self.send_alert(
                    subject="⚠️ CELERY SYSTEM DEGRADED",
                    message=f"""
Celery system is in DEGRADED state.

System Status: {overall_status.upper()}
Timestamp: {health_data.get('timestamp')}

Component Statuses:
- Workers: {health_data.get('workers', {}).get('status', 'unknown')}
- Active Tasks: {health_data.get('active_tasks', {}).get('status', 'unknown')}
- Queues: {health_data.get('queues', {}).get('status', 'unknown')}
- System Metrics: {health_data.get('system_metrics', {}).get('status', 'unknown')}
- Task Execution: {health_data.get('task_execution_test', {}).get('status', 'unknown')}

Performance may be impacted. Please investigate.
                    """.strip(),
                    alert_type='system_degraded'
                )
            
            # Check for specific issues
            self._check_worker_issues(health_data)
            self._check_queue_issues(health_data)
            self._check_system_issues(health_data)
            self._check_task_execution_issues(health_data)
            
            # Check performance issues
            self._check_performance_issues()
            
        except Exception as e:
            logger.error(f"Error in Celery health alert check: {e}")
    
    def _check_worker_issues(self, health_data):
        """Check for worker-specific issues."""
        workers = health_data.get('workers', {})
        
        if workers.get('status') == 'no_workers':
            self.send_alert(
                subject="🚨 NO CELERY WORKERS DETECTED",
                message=f"""
No active Celery workers were found.

This means no tasks are being processed.
Please check if Celery workers are running.

Timestamp: {health_data.get('timestamp')}
                """.strip(),
                alert_type='no_workers'
            )
        elif workers.get('status') == 'error':
            self.send_alert(
                subject="⚠️ CELERY WORKER ERROR",
                message=f"""
Error detected while checking Celery workers.

Error: {workers.get('error', 'Unknown error')}

Please check Celery worker logs.
Timestamp: {health_data.get('timestamp')}
                """.strip(),
                alert_type='worker_error'
            )
    
    def _check_queue_issues(self, health_data):
        """Check for queue-specific issues."""
        queues = health_data.get('queues', {})
        
        if queues.get('status') == 'no_queues':
            self.send_alert(
                subject="⚠️ NO CELERY QUEUES DETECTED",
                message=f"""
No active Celery queues were found.

This may indicate a configuration issue.
Please check Celery and broker configuration.

Timestamp: {health_data.get('timestamp')}
                """.strip(),
                alert_type='no_queues'
            )
        else:
            total_pending = queues.get('total_pending', 0)
            if total_pending > 1000:  # Alert if more than 1000 pending tasks
                self.send_alert(
                    subject="⚠️ HIGH QUEUE BACKLOG",
                    message=f"""
High number of pending tasks detected in Celery queues.

Total Pending Tasks: {total_pending}

This may indicate worker performance issues or system overload.
Please check worker capacity and task processing speed.

Timestamp: {health_data.get('timestamp')}
                """.strip(),
                    alert_type='high_backlog'
                )
    
    def _check_system_issues(self, health_data):
        """Check for system resource issues."""
        system_metrics = health_data.get('system_metrics', {})
        
        if system_metrics.get('status') == 'healthy':
            cpu_percent = system_metrics.get('system_cpu', 0)
            memory_percent = system_metrics.get('system_memory', {}).get('percent_used', 0)
            
            # High CPU alert
            if cpu_percent > 90:
                self.send_alert(
                    subject="⚠️ HIGH CPU USAGE",
                    message=f"""
High CPU usage detected on Celery server.

Current CPU Usage: {cpu_percent}%

This may impact task processing performance.
Please check system resources and worker load.

Timestamp: {health_data.get('timestamp')}
                    """.strip(),
                    alert_type='high_cpu'
                )
            
            # High memory alert
            if memory_percent > 90:
                self.send_alert(
                    subject="⚠️ HIGH MEMORY USAGE",
                    message=f"""
High memory usage detected on Celery server.

Current Memory Usage: {memory_percent}%

This may impact task processing performance.
Please check system resources and memory leaks.

Timestamp: {health_data.get('timestamp')}
                    """.strip(),
                    alert_type='high_memory'
                )
    
    def _check_task_execution_issues(self, health_data):
        """Check for task execution issues."""
        task_test = health_data.get('task_execution_test', {})
        
        if task_test.get('status') == 'timeout':
            self.send_alert(
                subject="🚨 CELERY TASK EXECUTION TIMEOUT",
                message=f"""
Celery task execution test timed out.

This indicates workers may not be responding or processing tasks correctly.

Test Timeout: {task_test.get('timeout_seconds', 'Unknown')} seconds
Task ID: {task_test.get('task_id', 'Unknown')}

Please check worker status and task processing.

Timestamp: {health_data.get('timestamp')}
                """.strip(),
                alert_type='task_timeout'
            )
        elif task_test.get('status') == 'error':
            self.send_alert(
                subject="🚨 CELERY TASK EXECUTION ERROR",
                message=f"""
Error detected during Celery task execution test.

Error: {task_test.get('error', 'Unknown error')}

This indicates a serious issue with task processing.
Please check Celery configuration and worker logs.

Timestamp: {health_data.get('timestamp')}
                """.strip(),
                alert_type='task_execution_error'
            )
    
    def _check_performance_issues(self):
        """Check for performance issues based on metrics."""
        try:
            # Get performance metrics for last hour
            perf_metrics = get_celery_performance_metrics(hours=1)
            
            if 'error' not in perf_metrics:
                summary = perf_metrics.get('summary', {})
                failure_rate = summary.get('failure_rate', 0)
                avg_duration = summary.get('average_duration', 0)
                
                # High failure rate alert
                if failure_rate > 20:  # More than 20% failure rate
                    self.send_alert(
                        subject="⚠️ HIGH TASK FAILURE RATE",
                        message=f"""
High task failure rate detected in the last hour.

Failure Rate: {failure_rate}%
Successful Tasks: {summary.get('successful_tasks', 0)}
Failed Tasks: {summary.get('failed_tasks', 0)}

This may indicate issues with task logic or external dependencies.
Please check recent task failures and error logs.

Timestamp: {datetime.utcnow().isoformat()}
                        """.strip(),
                        alert_type='high_failure_rate'
                    )
                
                # Slow task processing alert
                if avg_duration > 300:  # More than 5 minutes average
                    self.send_alert(
                        subject="⚠️ SLOW TASK PROCESSING",
                        message=f"""
Slow task processing detected in the last hour.

Average Task Duration: {avg_duration:.2f} seconds

This may indicate performance bottlenecks or resource contention.
Please check task performance and system resources.

Timestamp: {datetime.utcnow().isoformat()}
                        """.strip(),
                        alert_type='slow_processing'
                    )
        
        except Exception as e:
            logger.error(f"Error checking performance issues: {e}")


# Singleton instance
health_alerts = CeleryHealthAlerts()


def check_celery_health_alerts():
    """Convenience function to check and send Celery health alerts."""
    health_alerts.check_and_alert()


def send_celery_health_report():
    """Send daily health summary report."""
    try:
        # Only send report if configured
        if not health_alerts.email_recipients:
            return
        
        health_data = get_celery_health()
        perf_metrics = get_celery_performance_metrics(hours=24)
        error_trends = get_celery_error_trends(hours=24)
        
        # Create daily report
        report_date = datetime.utcnow().strftime('%Y-%m-%d')
        subject = f"📊 Daily Celery Health Report - {report_date}"
        
        message = f"""
Daily Celery Health Report - {report_date}

=== OVERALL STATUS ===
Status: {health_data.get('overall_status', 'unknown').upper()}
Health Check Time: {health_data.get('timestamp')}

=== PERFORMANCE SUMMARY (24h) ===
Total Tasks: {perf_metrics.get('summary', {}).get('total_tasks', 0)}
Success Rate: {perf_metrics.get('summary', {}).get('success_rate', 0):.1f}%
Average Duration: {perf_metrics.get('summary', {}).get('average_duration', 0):.2f}s

=== WORKER STATUS ===
Worker Count: {health_data.get('workers', {}).get('worker_count', 0)}
Total Processes: {health_data.get('workers', {}).get('total_processes', 0)}

=== QUEUE STATUS ===
Pending Tasks: {health_data.get('queues', {}).get('total_pending', 0)}

=== SYSTEM RESOURCES ===
CPU Usage: {health_data.get('system_metrics', {}).get('system_cpu', 0):.1f}%
Memory Usage: {health_data.get('system_metrics', {}).get('system_memory', {}).get('percent_used', 0):.1f}%

=== TOP ERRORS (24h) ===
{chr(10).join([f"- {err.get('exception_type', 'Unknown')}: {err.get('count', 0)} occurrences" for err in error_trends.get('error_types', [])[:5]])}

View detailed metrics: {getattr(settings, 'SITE_URL', '')}/userauth/celery/health/
        """.strip()
        
        # Send the report
        send_mail(
            subject=subject,
            message=message,
            from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@vault.local'),
            recipient_list=health_alerts.email_recipients,
            fail_silently=False,
        )
        
        logger.info(f"Daily Celery health report sent for {report_date}")
        
    except Exception as e:
        logger.error(f"Error sending daily Celery health report: {e}")
