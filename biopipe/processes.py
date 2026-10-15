"""Stop a process tree owned by a BioPipe job, never by executable name."""
import psutil


def stop_tree(process):
    if process.poll() is not None:
        return
    try:
        root = psutil.Process(process.pid)
        # Stop dispatch before enumerating descendants. Then freeze children
        # before terminating them, so a worker cannot spawn a replacement.
        root.suspend()
        children = root.children(recursive=True)
        for child in children:
            try: child.suspend()
            except psutil.NoSuchProcess: pass
        for child in reversed(children):
            try: child.kill()
            except psutil.NoSuchProcess: pass
        process.kill()
        process.wait(timeout=10)
        psutil.wait_procs(children, timeout=5)
    except psutil.NoSuchProcess:
        process.wait(timeout=10)
    finally:
        if process.poll() is None:
            try: psutil.Process(process.pid).resume()
            except psutil.NoSuchProcess: pass
