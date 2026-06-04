"""Scheduler stubs (Redis broker removed).

Celery and Redis were previously used for background tasks. The project
no longer includes Redis; these synchronous stubs keep the same function
names available for imports and local execution.
"""

def cleanup_old_results():
    # Placeholder: delete cached results older than retention
    return True


def run_scheduled_report(report_id: str):
    # Placeholder: fetch report config and run pipeline
    return {"report_id": report_id, "status": "scheduled_run_placeholder"}
