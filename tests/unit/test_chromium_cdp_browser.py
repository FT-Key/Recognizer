"""Tests de ChromiumCdpBrowser con mocks de cliente CDP y popen."""

import tempfile
from collections.abc import Sequence
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from recognizer.adapters.cdp_client import CdpTarget, JsonValue
from recognizer.adapters.chromium import BrowserFamily, DetectedBrowser
from recognizer.adapters.chromium_cdp import ChromiumCdpBrowser
from recognizer.core.domain.browser import TabKey, TabSpec
from recognizer.core.errors import ActionError

PROFILE_BASE = Path(tempfile.gettempdir()) / "recognizer-browser-tests"


def _detected() -> DetectedBrowser:
    return DetectedBrowser(family=BrowserFamily.CHROME, executable="C:\\chrome.exe")


def _tabs() -> dict[TabKey, TabSpec]:
    return {
        TabKey("video"): TabSpec(
            key=TabKey("video"),
            url="https://youtube.com/watch?v=abc",
            match="youtube.com",
        ),
    }


def _target(
    target_id: str = "t1",
    url: str = "https://youtube.com/watch?v=abc",
    ws_url: str = "ws://127.0.0.1:9222/devtools/page/t1",
) -> CdpTarget:
    return CdpTarget(
        id=target_id,
        url=url,
        title="Video",
        type="page",
        ws_url=ws_url,
    )


class FakeCdpClient:
    """Doble de CdpClient que registra llamadas y devuelve respuestas configurables."""

    def __init__(
        self,
        *,
        available: bool = True,
        targets: list[CdpTarget] | None = None,
        create_target_id: str = "new-1",
        evaluate_result: JsonValue = None,
    ) -> None:
        self._available = available
        self._targets = targets or []
        self._create_target_id = create_target_id
        self._evaluate_result = evaluate_result
        self.activate_calls: list[str] = []
        self.navigate_calls: list[tuple[str, str]] = []
        self.create_target_calls: int = 0
        self.evaluate_calls: list[tuple[str, str, bool]] = []
        self.key_down_calls: list[tuple[str, str, str, int, int]] = []
        self.key_up_calls: list[tuple[str, str, str, int, int]] = []

    def is_available(self) -> bool:
        return self._available

    def list_targets(self) -> tuple[CdpTarget, ...]:
        return tuple(self._targets)

    def create_target(self) -> str:
        self.create_target_calls += 1
        return self._create_target_id

    def activate_target(self, target_id: str) -> None:
        self.activate_calls.append(target_id)

    def navigate(self, target_id: str, url: str) -> None:
        self.navigate_calls.append((target_id, url))

    def evaluate(
        self,
        target_id: str,
        expression: str,
        *,
        await_promise: bool = True,
    ) -> JsonValue:
        self.evaluate_calls.append((target_id, expression, await_promise))
        return self._evaluate_result

    def dispatch_key_down(
        self,
        target_id: str,
        key: str,
        code: str,
        windows_virtual_key_code: int,
        modifiers: int = 0,
        text: str = "",  # noqa: ARG002
    ) -> None:
        self.key_down_calls.append((target_id, key, code, windows_virtual_key_code, modifiers))

    def dispatch_key_up(
        self,
        target_id: str,
        key: str,
        code: str,
        windows_virtual_key_code: int,
        modifiers: int = 0,
    ) -> None:
        self.key_up_calls.append((target_id, key, code, windows_virtual_key_code, modifiers))


class RecordingPopen:
    """Doble de popen que acumula los argv recibidos."""

    def __init__(self) -> None:
        self.argvs: list[tuple[str, ...]] = []

    def __call__(self, argv: Sequence[str]) -> object:
        self.argvs.append(tuple(argv))
        return MagicMock()


def _browser(
    client: FakeCdpClient | None = None,
    popen: RecordingPopen | None = None,
) -> tuple[ChromiumCdpBrowser, FakeCdpClient]:
    client = client or FakeCdpClient()
    popen = popen or RecordingPopen()
    browser = ChromiumCdpBrowser(
        tabs=_tabs(),
        detected=_detected(),
        profile_dir=PROFILE_BASE,
        popen=popen,
        client=client,  # type: ignore[arg-type]
    )
    return browser, client


class TestEnsure:
    def test_creates_target_if_not_exists(self) -> None:
        client = FakeCdpClient(available=True, targets=[])
        browser, _ = _browser(client=client)
        browser.ensure(tab=TabKey("video"), url="https://youtube.com/watch?v=abc")
        assert client.create_target_calls == 1
        assert client.navigate_calls == [("new-1", "https://youtube.com/watch?v=abc")]
        assert client.activate_calls == ["new-1"]

    def test_navigates_if_url_differs(self) -> None:
        existing = _target(url="https://youtube.com/watch?v=old")
        client = FakeCdpClient(available=True, targets=[existing])
        browser, _ = _browser(client=client)
        browser.ensure(tab=TabKey("video"), url="https://youtube.com/watch?v=new")
        assert client.navigate_calls == [("t1", "https://youtube.com/watch?v=new")]
        assert "t1" in client.activate_calls

    def test_just_activates_if_url_matches(self) -> None:
        existing = _target(url="https://youtube.com/watch?v=abc")
        client = FakeCdpClient(available=True, targets=[existing])
        browser, _ = _browser(client=client)
        browser.ensure(tab=TabKey("video"), url="https://youtube.com/watch?v=abc")
        assert client.navigate_calls == []
        assert "t1" in client.activate_calls

    def test_ensure_plays_video(self) -> None:
        existing = _target(url="https://youtube.com/watch?v=abc")
        client = FakeCdpClient(available=True, targets=[existing], evaluate_result=None)
        browser, _ = _browser(client=client)
        browser.ensure(tab=TabKey("video"), url="https://youtube.com/watch?v=abc")
        play_calls = [
            (tid, expr, af) for tid, expr, af in client.evaluate_calls if "play()" in expr
        ]
        assert len(play_calls) == 1
        assert play_calls[0][2] is False

    def test_ensure_launches_chrome_if_not_running(self) -> None:
        popen = RecordingPopen()
        availability_sequence = [False, False, True]
        call_count = [0]

        class SequentialClient(FakeCdpClient):
            def is_available(self) -> bool:
                idx = min(call_count[0], len(availability_sequence) - 1)
                call_count[0] += 1
                return availability_sequence[idx]

        client = SequentialClient()
        browser, _ = _browser(client=client, popen=popen)
        browser._ensure_running()

        assert len(popen.argvs) == 1
        args = popen.argvs[0]
        assert args[0] == "C:\\chrome.exe"
        assert "--remote-debugging-port=9222" in args
        user_data_args = [arg for arg in args if arg.startswith("--user-data-dir=")]
        assert len(user_data_args) == 1
        profile_arg = Path(user_data_args[0].removeprefix("--user-data-dir="))
        assert profile_arg.is_absolute()
        assert profile_arg.name == "chrome"
        assert profile_arg.parent.name == "browser-profile"

    def test_ensure_running_already_available(self) -> None:
        client = FakeCdpClient(available=True)
        popen = RecordingPopen()
        browser = ChromiumCdpBrowser(
            tabs=_tabs(),
            detected=_detected(),
            profile_dir=PROFILE_BASE,
            popen=popen,
            client=client,  # type: ignore[arg-type]
        )
        browser._ensure_running()
        assert popen.argvs == []

    def test_ensure_raises_on_unregistered_tab(self) -> None:
        client = FakeCdpClient(available=True)
        browser, _ = _browser(client=client)
        with pytest.raises(ActionError, match="Pestana no registrada"):
            browser.ensure(tab=TabKey("unknown"), url="https://x.com")

    def test_ensure_popen_error_raises_action_error(self) -> None:
        def failing_popen(argv: Sequence[str]) -> object:
            del argv
            msg = "no se pudo lanzar"
            raise OSError(msg)

        client = FakeCdpClient(available=False)
        browser = ChromiumCdpBrowser(
            tabs=_tabs(),
            detected=_detected(),
            profile_dir=PROFILE_BASE,
            popen=failing_popen,
            client=client,  # type: ignore[arg-type]
        )
        with pytest.raises(ActionError, match="No se pudo lanzar el navegador"):
            browser.ensure(tab=TabKey("video"), url="https://youtube.com/watch?v=abc")

    def test_ensure_popen_timeout_raises_action_error(self) -> None:
        client = FakeCdpClient(available=False)
        popen = RecordingPopen()
        browser = ChromiumCdpBrowser(
            tabs=_tabs(),
            detected=_detected(),
            profile_dir=PROFILE_BASE,
            popen=popen,
            client=client,  # type: ignore[arg-type]
        )
        import time as _time

        original_sleep = _time.sleep

        _time.sleep = lambda _s: None
        try:
            with pytest.raises(ActionError, match="Chromium no respondio"):
                browser._ensure_running()
        finally:
            _time.sleep = original_sleep


class TestSeekMedia:
    def test_seek_calls_evaluate(self) -> None:
        existing = _target()
        client = FakeCdpClient(available=True, targets=[existing], evaluate_result="ok")
        browser, _ = _browser(client=client)
        browser.seek_media(tab=TabKey("video"), fraction=0.4)
        seek_calls = [
            (tid, expr, af) for tid, expr, af in client.evaluate_calls if "currentTime" in expr
        ]
        assert len(seek_calls) == 1
        _, expression, _ = seek_calls[0]
        assert "0.4" in expression

    def test_seek_no_video_raises(self) -> None:
        existing = _target()
        client = FakeCdpClient(available=True, targets=[existing], evaluate_result="no-video")
        browser, _ = _browser(client=client)
        with pytest.raises(ActionError, match="No se encontro elemento <video>"):
            browser.seek_media(tab=TabKey("video"), fraction=0.5)

    def test_seek_no_target_raises(self) -> None:
        client = FakeCdpClient(available=True, targets=[])
        browser, _ = _browser(client=client)
        with pytest.raises(ActionError, match="No se encontro la pestana"):
            browser.seek_media(tab=TabKey("video"), fraction=0.5)

    def test_seek_not_available_raises(self) -> None:
        client = FakeCdpClient(available=False)
        browser, _ = _browser(client=client)
        with pytest.raises(ActionError, match="no esta disponible"):
            browser.seek_media(tab=TabKey("video"), fraction=0.5)

    def test_seek_unregistered_tab_raises(self) -> None:
        client = FakeCdpClient(available=True)
        browser, _ = _browser(client=client)
        with pytest.raises(ActionError, match="Pestana no registrada"):
            browser.seek_media(tab=TabKey("bad"), fraction=0.5)


class TestPressKeys:
    def test_press_keys_dispatches_key_events(self) -> None:
        existing = _target()
        client = FakeCdpClient(available=True, targets=[existing])
        browser, _ = _browser(client=client)
        browser.press_keys(tab=TabKey("video"), keys=("a", "b"))
        assert len(client.key_down_calls) == 2
        assert len(client.key_up_calls) == 2
        assert client.key_down_calls[0][1] == "a"
        assert client.key_down_calls[1][1] == "b"

    def test_press_keys_special_key(self) -> None:
        existing = _target()
        client = FakeCdpClient(available=True, targets=[existing])
        browser, _ = _browser(client=client)
        browser.press_keys(tab=TabKey("video"), keys=("enter",))
        assert client.key_down_calls[0][1] == "Enter"
        assert client.key_down_calls[0][2] == "Enter"
        assert client.key_down_calls[0][3] == 13

    def test_press_keys_no_target_raises(self) -> None:
        client = FakeCdpClient(available=True, targets=[])
        browser, _ = _browser(client=client)
        with pytest.raises(ActionError, match="No se encontro la pestana"):
            browser.press_keys(tab=TabKey("video"), keys=("a",))

    def test_press_keys_not_available_raises(self) -> None:
        client = FakeCdpClient(available=False)
        browser, _ = _browser(client=client)
        with pytest.raises(ActionError, match="no esta disponible"):
            browser.press_keys(tab=TabKey("video"), keys=("a",))

    def test_press_keys_unregistered_tab_raises(self) -> None:
        client = FakeCdpClient(available=True)
        browser, _ = _browser(client=client)
        with pytest.raises(ActionError, match="Pestana no registrada"):
            browser.press_keys(tab=TabKey("bad"), keys=("a",))


class TestFindTarget:
    def test_prefers_playing(self) -> None:
        paused_target = _target(target_id="paused", url="https://youtube.com/watch?v=abc")
        playing_target = _target(target_id="playing", url="https://youtube.com/watch?v=abc")

        call_count = [0]

        def selective_evaluate(
            target_id: str,
            expression: str,
            *,
            await_promise: bool = True,
        ) -> JsonValue:
            del expression, await_promise
            call_count[0] += 1
            return target_id != "playing"

        client = FakeCdpClient(
            available=True,
            targets=[paused_target, playing_target],
        )
        client.evaluate = selective_evaluate  # type: ignore[method-assign]
        browser = ChromiumCdpBrowser(
            tabs=_tabs(),
            detected=_detected(),
            profile_dir=PROFILE_BASE,
            popen=RecordingPopen(),
            client=client,  # type: ignore[arg-type]
        )
        target = browser._find_target("youtube.com")
        assert target is not None
        assert target.id == "playing"

    def test_prefers_exact_url(self) -> None:
        partial = _target(target_id="partial", url="https://youtube.com/results?v=abc")
        exact = _target(target_id="exact", url="https://youtube.com/watch?v=abc")

        def no_playing(
            target_id: str,
            expression: str,
            *,
            await_promise: bool = True,
        ) -> JsonValue:
            del target_id, expression, await_promise
            return True

        client = FakeCdpClient(available=True, targets=[partial, exact])
        client.evaluate = no_playing  # type: ignore[method-assign]
        browser = ChromiumCdpBrowser(
            tabs=_tabs(),
            detected=_detected(),
            profile_dir=PROFILE_BASE,
            popen=RecordingPopen(),
            client=client,  # type: ignore[arg-type]
        )
        target = browser._find_target("youtube.com")
        assert target is not None
        assert target.id == "partial"

    def test_returns_none_if_no_match(self) -> None:
        client = FakeCdpClient(
            available=True,
            targets=[_target(url="https://other.com")],
        )
        browser = ChromiumCdpBrowser(
            tabs=_tabs(),
            detected=_detected(),
            profile_dir=PROFILE_BASE,
            popen=RecordingPopen(),
            client=client,  # type: ignore[arg-type]
        )
        assert browser._find_target("youtube.com") is None
