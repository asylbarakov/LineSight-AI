"""Ошибки пайплайна с кодами из контракта API."""

E_VIDEO_INVALID = "E_VIDEO_INVALID"
E_DECODE = "E_DECODE"
E_MODEL = "E_MODEL"
E_TIMEOUT = "E_TIMEOUT"

ERROR_CODES = (E_VIDEO_INVALID, E_DECODE, E_MODEL, E_TIMEOUT)


class PipelineError(Exception):
    """Ошибка обработки видео; `code` попадает в `inspection.error_code`."""

    def __init__(self, code: str, message: str = ""):
        if code not in ERROR_CODES:
            raise ValueError(f"Неизвестный код ошибки: {code}")
        super().__init__(message or code)
        self.code = code
        self.message = message or code
