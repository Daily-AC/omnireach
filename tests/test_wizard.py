import pytest

from omnireach.adapters.base import AdapterBase
from omnireach.contract import SearchResult
from omnireach.installer import InstallError
from omnireach.registry import Dep, SourceSpec
from omnireach.wizard import (
    SetupReport,
    StepKind,
    StepStatus,
    WizardStep,
    run_setup,
)


class _StubAdapter(AdapterBase):
    name = "stub"

    def __init__(self, ready: bool = True) -> None:
        self._ready = ready

    async def is_ready(self) -> bool:
        return self._ready

    async def search(self, query, *, limit=10):
        return []


def _spec(auto: list[Dep] | None = None, manual: list[Dep] | None = None) -> SourceSpec:
    return SourceSpec(
        id="stub",
        tier="one_step",
        adapter="tests.test_wizard._StubAdapter",
        description="stub",
        deps_auto=auto or [],
        deps_manual=manual or [],
    )


async def test_setup_skips_when_adapter_already_ready():
    """If is_ready() already True, wizard returns SKIPPED for all steps."""
    spec = _spec(auto=[Dep(kind="pipx", name="agent-reach")])
    report = await run_setup(
        spec,
        adapter=_StubAdapter(ready=True),
        confirm=lambda msg: True,
        run_install=lambda kind, name: None,
        prompt_user_step=lambda step: None,
    )
    assert report.already_ready is True
    assert all(s.status == StepStatus.SKIPPED for s in report.steps)


async def test_setup_runs_auto_install_then_manual_then_verifies():
    """Happy path: pipx install runs, manual step prompts user, final is_ready() True."""
    installs: list[tuple[str, str]] = []

    spec = _spec(
        auto=[Dep(kind="pipx", name="agent-reach"), Dep(kind="npm", name="rdt-cli")],
        manual=[Dep(step="跑 `rdt login`")],
    )

    adapter = _StubAdapter(ready=False)

    def run_install(kind: str, name: str) -> None:
        installs.append((kind, name))
        adapter._ready = True  # simulate post-install readiness

    prompts: list[str] = []

    def prompt_user_step(step: Dep) -> None:
        prompts.append(step.step)

    report = await run_setup(
        spec,
        adapter=adapter,
        confirm=lambda msg: True,
        run_install=run_install,
        prompt_user_step=prompt_user_step,
    )

    assert installs == [("pipx", "agent-reach"), ("npm", "rdt-cli")]
    assert prompts == ["跑 `rdt login`"]
    assert report.success is True
    assert report.already_ready is False
    assert [s.kind for s in report.steps] == [StepKind.AUTO, StepKind.AUTO, StepKind.MANUAL, StepKind.VERIFY]
    assert all(s.status == StepStatus.OK for s in report.steps)


async def test_setup_aborts_when_user_declines_confirmation():
    spec = _spec(auto=[Dep(kind="pipx", name="agent-reach")])
    report = await run_setup(
        spec,
        adapter=_StubAdapter(ready=False),
        confirm=lambda msg: False,  # user declines
        run_install=lambda kind, name: None,
        prompt_user_step=lambda step: None,
    )
    assert report.success is False
    assert report.aborted is True


async def test_setup_marks_failed_install_step():
    spec = _spec(auto=[Dep(kind="pipx", name="agent-reach")])

    def run_install(kind: str, name: str) -> None:
        raise InstallError(name, "pipx blew up", hint="install pipx first")

    report = await run_setup(
        spec,
        adapter=_StubAdapter(ready=False),
        confirm=lambda msg: True,
        run_install=run_install,
        prompt_user_step=lambda step: None,
    )
    assert report.success is False
    assert any(s.kind == StepKind.AUTO and s.status == StepStatus.FAILED for s in report.steps)
    failed = next(s for s in report.steps if s.status == StepStatus.FAILED)
    assert "pipx blew up" in (failed.detail or "")


async def test_setup_verify_fails_when_adapter_still_not_ready():
    spec = _spec(auto=[Dep(kind="pipx", name="agent-reach")])
    adapter = _StubAdapter(ready=False)  # stays not-ready after install

    report = await run_setup(
        spec,
        adapter=adapter,
        confirm=lambda msg: True,
        run_install=lambda kind, name: None,
        prompt_user_step=lambda step: None,
    )
    assert report.success is False
    verify_step = next(s for s in report.steps if s.kind == StepKind.VERIFY)
    assert verify_step.status == StepStatus.FAILED
