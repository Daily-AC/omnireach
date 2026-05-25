"""Wizard — drive a source's setup flow.

The wizard is dependency-injected: tests pass stubs for `confirm`,
`run_install`, `prompt_user_step`, and `run_verify`. The CLI subcommand
wires them to Click prompts + installer.py + subprocess.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Callable

from omnireach.adapters.base import AdapterBase
from omnireach.installer import InstallError
from omnireach.registry import Dep, SourceSpec


class StepKind(str, Enum):
    AUTO = "auto"
    MANUAL = "manual"
    VERIFY = "verify"


class StepStatus(str, Enum):
    OK = "ok"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class WizardStep:
    kind: StepKind
    label: str
    status: StepStatus
    detail: str | None = None


@dataclass
class SetupReport:
    source_id: str
    steps: list[WizardStep] = field(default_factory=list)
    already_ready: bool = False
    aborted: bool = False

    @property
    def success(self) -> bool:
        if self.aborted:
            return False
        if not self.steps:
            return False
        return all(s.status in (StepStatus.OK, StepStatus.SKIPPED) for s in self.steps)


ConfirmFn = Callable[[str], bool]
InstallFn = Callable[[str, str], None]
PromptFn = Callable[[Dep], None]
RunVerifyFn = Callable[[str], tuple[int, str]]


def _noop_verify(cmd: str) -> tuple[int, str]:  # pragma: no cover - default fallback
    return (0, "")


async def run_setup(
    spec: SourceSpec,
    *,
    adapter: AdapterBase,
    confirm: ConfirmFn,
    run_install: InstallFn,
    prompt_user_step: PromptFn,
    run_verify: RunVerifyFn = _noop_verify,
) -> SetupReport:
    """Drive a source through its setup steps. Returns a structured report.

    Pre-check: if adapter.is_ready() is already True, return immediately with
    all steps marked SKIPPED.

    Otherwise:
      1. Confirm overall flow with the user.
      2. For each auto dep, call run_install(kind, name); on InstallError, mark step FAILED and stop.
      3. For each manual dep, call prompt_user_step(dep). If dep.verify is set,
         run_verify(dep.verify) — exit 0 = MANUAL OK, non-zero = MANUAL FAILED + early-return
         (with combined output captured as `detail`).
      4. Re-probe adapter.is_ready(). VERIFY step is OK iff ready, FAILED otherwise.
    """
    report = SetupReport(source_id=spec.id)

    if await adapter.is_ready():
        report.already_ready = True
        for dep in spec.deps_auto:
            report.steps.append(WizardStep(StepKind.AUTO, f"{dep.kind} install {dep.name}", StepStatus.SKIPPED))
        for dep in spec.deps_manual:
            report.steps.append(WizardStep(StepKind.MANUAL, dep.step, StepStatus.SKIPPED))
        report.steps.append(WizardStep(StepKind.VERIFY, "is_ready()", StepStatus.SKIPPED))
        return report

    if not confirm(f"开始配置 '{spec.id}'?"):
        report.aborted = True
        return report

    for dep in spec.deps_auto:
        label = f"{dep.kind} install {dep.name}"
        try:
            run_install(dep.kind, dep.name)
            report.steps.append(WizardStep(StepKind.AUTO, label, StepStatus.OK))
        except InstallError as e:
            report.steps.append(
                WizardStep(StepKind.AUTO, label, StepStatus.FAILED, detail=str(e))
            )
            return report

    for dep in spec.deps_manual:
        prompt_user_step(dep)
        if dep.verify:
            code, out = run_verify(dep.verify)
            if code != 0:
                report.steps.append(
                    WizardStep(StepKind.MANUAL, dep.step, StepStatus.FAILED, detail=out.strip() or f"verify exited {code}")
                )
                return report
        report.steps.append(WizardStep(StepKind.MANUAL, dep.step, StepStatus.OK))

    ready = await adapter.is_ready()
    report.steps.append(
        WizardStep(
            StepKind.VERIFY,
            "is_ready()",
            StepStatus.OK if ready else StepStatus.FAILED,
            detail=None if ready else "adapter still not ready after setup",
        )
    )
    return report
