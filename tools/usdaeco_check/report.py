"""The family check.py PASS/FAIL/NOT RUN convention, reusable by every library."""
from dataclasses import dataclass


@dataclass(frozen=True)
class Result:
    name: str
    ok: bool | None
    detail: str = ""

    def __bool__(self):
        return self.ok is True

    @property
    def status(self):
        return "NOT RUN" if self.ok is None else "PASS" if self.ok else "FAIL"


class Report:
    def __init__(self):
        self.results = []

    def check(self, name, ok, detail=""):
        return self.add(Result(name, bool(ok), detail))

    def not_run(self, name, detail):
        """Record an unexecuted check with its cause, without claiming a pass."""
        if not detail.strip():
            raise ValueError("NOT RUN requires a cause")
        return self.add(Result(name, None, detail))

    def add(self, result):
        if not isinstance(result, Result):
            raise TypeError("Report.add expects a Result")
        self.results.append(result)
        print(f"{result.status}  {result.name}"
              + (f"  — {result.detail}" if result.detail else ""), flush=True)
        return bool(result)

    def run(self, name, function, *args, **kwargs):
        """Record an exception as a failure and let the remaining checks run."""
        try:
            result = function(*args, **kwargs)
            return self.add(Result(name, result.ok if isinstance(result, Result) else bool(result),
                                   result.detail if isinstance(result, Result) else ""))
        except Exception as exc:
            return self.check(name, False, f"{type(exc).__name__}: {exc}")

    @property
    def failed(self):
        return sum(result.ok is False for result in self.results)

    @property
    def not_run_count(self):
        return sum(result.ok is None for result in self.results)

    def finish(self):
        """Print the core summary and return a process exit code."""
        print(f"\n{len(self.results)} checks, {self.failed} failed, {self.not_run_count} not run")
        return int(bool(self.failed))

    def exit(self):
        raise SystemExit(self.finish())
