"""Bounded agent-facing views; scientific execution remains in Application."""
import math
import time
from urllib.parse import quote


ACTIVE = {'queued', 'preparing', 'uploading', 'running', 'waiting_connection'}


def job_view(job, view='brief'):
    if view not in ('brief', 'full'):
        raise ValueError('view must be brief or full')
    if view == 'full':
        return job
    keys = ('id', 'name', 'status', 'progress', 'error', 'queued_reason', 'created_at',
            'started_at', 'finished_at', 'request_id', 'reused', 'wait_timed_out')
    result = {key: job[key] for key in keys if key in job}
    if job.get('id'):
        result['artifacts_href'] = '/api/v1/jobs/' + quote(job['id'], safe='') + '/artifacts'
    return result


def wait_job(client, job, timeout=30, *, view='brief', on_update=None):
    if isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or not math.isfinite(timeout) or timeout < 0:
        raise ValueError('timeout must be a finite non-negative number')
    job_view(job, view)  # Validate before any polling.
    deadline = time.monotonic() + timeout if timeout else None
    receipt = {key: job[key] for key in ('request_id', 'reused') if key in job}
    path = '/v1/jobs/' + quote(job['id'], safe='') + '?view=brief'
    if on_update:
        on_update(job)
    while job['status'] in ACTIVE:
        remaining = deadline - time.monotonic() if deadline is not None else .5
        if remaining <= 0:
            if view == 'full':
                job = client.request('/v1/jobs/' + quote(job['id'], safe=''))
            return job_view({**job, **receipt, 'wait_timed_out': True}, view)
        time.sleep(min(.5, remaining))
        job = client.request(path)
        if on_update:
            on_update(job)
    if view == 'full':
        job = client.request('/v1/jobs/' + quote(job['id'], safe=''))
    return job_view({**job, **receipt}, view)


def log_view(value, encoding='text'):
    if encoding not in ('text', 'base64', 'both'):
        raise ValueError('encoding must be text, base64 or both')
    return {key: item for key, item in value.items()
            if encoding == 'both' or key not in ('text', 'base64') or key == encoding}
