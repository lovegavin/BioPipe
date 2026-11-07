"""Small third-party client: run/reconnect, inspect links, copy a selected native result.

Install Operon in this Python environment. No desktop or MCP client is needed.
"""
import argparse
import json
from pathlib import Path
from urllib.parse import urlencode

from operon.agent_views import wait_job
from operon.cli import read_graph_file
from operon.client import Client, data_directory


def run_workflow(client, graph, request_id, *, timeout=60):
    prepared = client.request('/v1/workflows/prepare', {'graph': graph})
    client.request('/v1/workflows/validate', {'graph': prepared, 'require_files': True})
    receipt = client.request('/v1/jobs', {'graph': prepared, 'request_id': request_id})
    job = wait_job(client, receipt, timeout, view='brief')
    return {'job': job, 'results': client.request(f'/v1/jobs/{job["id"]}/artifacts')}


def copy_result(client, index, href, output, *, role=None):
    """Only copy a link actually returned by this job's artifact index."""
    allowed = {item['href'] for group in ('artifacts', 'reports', 'figures')
               for item in index.get(group, []) if item.get('href')}
    if href not in allowed or not href.startswith('/api/v1/jobs/' + index['job_id'] + '/'):
        raise ValueError('Choose an exact href from this job artifact index')
    if role:
        if href not in {item.get('href') for item in index.get('artifacts', [])}:
            raise ValueError('A file role only applies to a native artifact')
        href += ('&' if '?' in href else '?') + urlencode({'role': role})
    return client.download(href.removeprefix('/api'), Path(output))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workspace', type=Path, required=True)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument('--workflow', type=Path)
    source.add_argument('--job')
    parser.add_argument('--request-id', help='Required for submission; reuse for identical retries')
    parser.add_argument('--timeout', type=float, default=60)
    parser.add_argument('--href', help='Exact result href printed by the previous invocation')
    parser.add_argument('--role', help='Optional native file role, obtained from the artifact preview')
    parser.add_argument('--output', type=Path, help='Destination for the explicitly selected result')
    args = parser.parse_args(argv)
    if args.workflow and not args.request_id:
        parser.error('--workflow requires --request-id')
    if bool(args.href) != bool(args.output) or args.role and not args.href:
        parser.error('Use --href and --output together; --role requires a selected href')
    workspace = args.workspace.resolve()
    client = Client(data_directory(workspace=workspace), workspace=workspace,
                    name='third-party-example', scopes=['context', 'run'] if args.workflow else ['context'],
                    auto_start=True, require_api=1)
    try:
        if args.workflow:
            result = run_workflow(client, read_graph_file(args.workflow), args.request_id, timeout=args.timeout)
        else:
            result = {'job': client.request('/v1/jobs/' + args.job + '?view=brief'),
                      'results': client.request('/v1/jobs/' + args.job + '/artifacts')}
        if args.href:
            result['copied'] = copy_result(client, result['results'], args.href, args.output, role=args.role)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        job = result['job']
        if job.get('wait_timed_out'):
            return 124
        return 1 if job['status'] in ('failed', 'cancelled', 'interrupted') else 0
    finally:
        # Disconnect only: jobs and the shared service remain available.
        client.close()


if __name__ == '__main__':
    raise SystemExit(main())
