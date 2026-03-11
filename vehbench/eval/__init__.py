from .runtime import TaskSession, build_request_from_task, load_tasks


def run_benchmark(*args, **kwargs):
    from .runner import run_benchmark as _run_benchmark

    return _run_benchmark(*args, **kwargs)


def summarize_run(*args, **kwargs):
    from .runner import summarize_run as _summarize_run

    return _summarize_run(*args, **kwargs)
