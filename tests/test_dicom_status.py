import unittest

from pydicom.dataset import Dataset

from module.utils.dicom_status import (
    check_c_move_responses,
    check_c_store_response,
    iter_c_find_responses,
)


def status(code: int) -> Dataset:
    response = Dataset()
    response.Status = code
    return response


class DicomStatusTests(unittest.TestCase):
    def test_move_consumes_pending_responses_and_returns_success(self):
        consumed = []

        def responses():
            for code in (0xFF00, 0xFF00, 0x0000):
                consumed.append(code)
                yield status(code), None

        self.assertEqual(check_c_move_responses(responses(), "test"), (1, ""))
        self.assertEqual(consumed, [0xFF00, 0xFF00, 0x0000])

    def test_move_returns_error_for_failure_warning_cancel_and_missing_status(self):
        for response in (None, Dataset(), status(0xA801), status(0xB000), status(0xFE00)):
            with self.subTest(response=response):
                passed, message = check_c_move_responses([(response, None)], "C-MOVE test")
                self.assertEqual(passed, 0)
                self.assertIn("C-MOVE test", message)
                self.assertTrue(message)

    def test_move_requires_final_response(self):
        for responses in ([], [(status(0xFF00), None)]):
            with self.subTest(responses=responses):
                self.assertEqual(
                    check_c_move_responses(responses, "test"),
                    (0, "test: no final response"),
                )

    def test_store_returns_success(self):
        self.assertEqual(check_c_store_response(status(0x0000), "test"), (1, ""))

    def test_store_returns_readable_error_and_logs_it(self):
        with self.assertLogs("module.utils.dicom_status", level="ERROR"):
            self.assertEqual(
                check_c_store_response(status(0xA700), "C-STORE test"),
                (0, "C-STORE test: status 0xA700"),
            )

    def test_store_missing_response_is_not_success(self):
        for response in (None, Dataset()):
            self.assertEqual(
                check_c_store_response(response, "test"), (0, "test: no response status")
            )

    def test_find_yields_matches_and_requires_final_success(self):
        first = Dataset()
        second = Dataset()
        results = list(iter_c_find_responses([
            (status(0xFF00), first),
            (status(0xFF01), second),
            (status(0x0000), None),
        ], "test"))
        self.assertEqual(len(results), 2)
        self.assertIs(results[0], first)
        self.assertIs(results[1], second)

    def test_find_accepts_successful_empty_result(self):
        self.assertEqual(
            list(iter_c_find_responses([(status(0x0000), None)], "test")), []
        )

    def test_find_does_not_return_success_shaped_results_on_failure(self):
        for responses in (
            [], [(None, None)], [(status(0xFF00), None)],
            [(status(0xFF00), Dataset())], [(status(0xA700), None)],
        ):
            with self.subTest(responses=responses):
                with self.assertRaises(RuntimeError):
                    list(iter_c_find_responses(responses, "test"))


if __name__ == "__main__":
    unittest.main()
