import logging
from collections.abc import Iterable, Iterator

from pydicom.dataset import Dataset

logger = logging.getLogger(__name__)


def transfer_failure(message: str) -> tuple[int, str]:
    logger.error(message)
    return 0, message


def check_c_store_response(status: Dataset | None, context: str) -> tuple[int, str]:
    code = getattr(status, "Status", None)
    if code == 0x0000:
        return 1, ""
    detail = f"status 0x{code:04X}" if isinstance(code, int) else "no response status"
    return transfer_failure(f"{context}: {detail}")


def check_c_move_responses(
    responses: Iterable[tuple[Dataset | None, Dataset | None]],
    context: str,
) -> tuple[int, str]:
    for status, _ in responses:
        if getattr(status, "Status", None) == 0xFF00:
            continue
        return check_c_store_response(status, context)
    return transfer_failure(f"{context}: no final response")


def iter_c_find_responses(
    responses: Iterable[tuple[Dataset | None, Dataset | None]],
    context: str,
) -> Iterator[Dataset]:
    for status, identifier in responses:
        if getattr(status, "Status", None) in (0xFF00, 0xFF01):
            if identifier is None:
                _, message = transfer_failure(f"{context}: missing query result")
                raise RuntimeError(message)
            yield identifier
        else:
            passed, message = check_c_store_response(status, context)
            if not passed:
                raise RuntimeError(message)
            return
    _, message = transfer_failure(f"{context}: no final query response")
    raise RuntimeError(message)
