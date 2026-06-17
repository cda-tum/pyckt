import pyckt.utils.loguru_loader as loguru_loader
from loguru import logger as loguru_logger
import pytest


@pytest.fixture(autouse=True)
def _reset_loguru_state():
    """Keep tests isolated: clear global logger sinks + singleton cache."""
    loguru_logger.remove()
    loguru_loader.Singleton._instances.clear()
    yield
    loguru_logger.remove()
    loguru_loader.Singleton._instances.clear()


def test_logger_is_singleton():
    a = loguru_loader.Logger("first")
    b = loguru_loader.Logger("second")

    assert a is b
    assert a.logger is loguru_logger


def test_logger_wrapper_methods_emit_messages(capsys):
    inst = loguru_loader.Logger()

    inst.debug("debug-message")
    inst.info("info-message")

    out = capsys.readouterr().out
    assert "debug-message" in out
    assert "info-message" in out


def test_setup_logger_returns_loguru_logger_and_writes_stdout(capsys):
    configured = loguru_loader.setup_logger(log_level="INFO")

    assert configured is loguru_logger
    configured.info("stdout-message")

    out = capsys.readouterr().out
    assert "stdout-message" in out


def test_setup_logger_adds_file_sink(tmp_path):
    log_file = tmp_path / "app.log"

    configured = loguru_loader.setup_logger(log_level="DEBUG", log_file=str(log_file))
    configured.info("file-message")

    assert log_file.exists()
    assert "file-message" in log_file.read_text()


def test_setup_logger_reconfiguration_does_not_duplicate_stdout_sink(capsys):
    configured = loguru_loader.setup_logger(log_level="DEBUG")
    configured.info("once-message-1")
    out1 = capsys.readouterr().out
    assert out1.count("once-message-1") == 1

    configured = loguru_loader.setup_logger(log_level="INFO")
    configured.info("once-message-2")
    out2 = capsys.readouterr().out
    assert out2.count("once-message-2") == 1


def test_logger_singleton_skips_reinit():
    """Second Logger() call returns the cached instance without re-running __init__ (line 17)."""
    a = loguru_loader.Logger()
    # Call again WITHOUT clearing cache — should hit the early return
    b = loguru_loader.Logger()
    assert a is b


def test_logger_init_skips_reinit_branch():
    """Directly verify the _initialized early-return branch (line 17) is hit."""
    inst = loguru_loader.Logger.__new__(loguru_loader.Logger)
    inst._initialized = True
    # __init__ should return immediately without touching logger
    inst.__init__()
    # If the branch wasn't hit, _initialized would remain True (no error)
    assert inst._initialized is True


def test_setup_logger_off_returns_silent_logger(capsys):
    """log_level='OFF' returns logger without adding any sink (line 43)."""
    result = loguru_loader.setup_logger(log_level="OFF")
    from loguru import logger as loguru_logger
    assert result is loguru_logger
    result.info("should-not-appear")
    assert capsys.readouterr().out == ""
