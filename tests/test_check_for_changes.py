import ast
import datetime
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock

from pydicom.dataset import Dataset

from sqlmodel import Session, create_engine, select

from module.Dataclasses import export_logger_dataclass
from module.utils.dicom_status import check_c_move_responses, transfer_failure


class CheckForChangesTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite://")
        with self.engine.begin() as connection:
            connection.exec_driver_sql(
                "CREATE TABLE DicomTransfer "
                "(DicomTransferId INTEGER PRIMARY KEY, PatientSer TEXT, SentDt TEXT)"
            )
            connection.exec_driver_sql(
                "CREATE TABLE RTPlan "
                "(RtPlanId INTEGER PRIMARY KEY, DicomTransferId INTEGER, PlanSopUid TEXT)"
            )
            connection.exec_driver_sql(
                "CREATE TABLE DicomObject "
                "(DicomObjectId INTEGER PRIMARY KEY, RtPlanId INTEGER, "
                "Modality TEXT, TypeUid TEXT, ReferenceUid TEXT, TransferStatus INTEGER)"
            )
        self.addCleanup(self.engine.dispose)
        # Load the actual function without importing orchestrator's production config/engines.
        source = (
            Path(__file__).resolve().parents[1]
            / "module" / "utils" / "orchestrator.py"
        )
        tree = ast.parse(source.read_text(encoding="utf-8"))
        function = next(
            node for node in tree.body
            if isinstance(node, ast.FunctionDef) and node.name == "check_for_changes_and_errors"
        )
        namespace = {
            "Session": Session,
            "select": select,
            "export_logger_dataclass": export_logger_dataclass,
            "log_database": SimpleNamespace(engine=self.engine),
        }
        exec(compile(ast.Module(body=[function], type_ignores=[]), str(source), "exec"), namespace)
        self.check_for_changes = namespace["check_for_changes_and_errors"]
        self.plan_set = {
            "PatientSer": 42,
            "PlanSet": {
                "plan-1": {
                    "RTPlanLabel": "label",
                    "RTPLAN": {"plan-1"},
                    "RTDOSE": {"dose-1"},
                    "RTRECORD": set(),
                    "RTSTRUCT": set(),
                    "CT": set(),
                }
            },
        }

    def add_history(self, transfer_id=1, patient="42", sent="2026-01-01",
                    plan="plan-1", objects=None, transfer_status=1):
        if objects is None:
            objects = [
                ("RTPLAN", "SOP_INSTANCE", plan),
                ("RTDOSE", "SOP_INSTANCE", "dose-1"),
            ]
        with self.engine.begin() as connection:
            connection.exec_driver_sql(
                "INSERT INTO DicomTransfer VALUES (?, ?, ?)", (transfer_id, patient, sent)
            )
            connection.exec_driver_sql(
                "INSERT INTO RTPlan VALUES (?, ?, ?)", (transfer_id, transfer_id, plan)
            )
            for modality, type_uid, uid in objects:
                connection.exec_driver_sql(
                    "INSERT INTO DicomObject (RtPlanId, Modality, TypeUid, ReferenceUid, TransferStatus) "
                    "VALUES (?, ?, ?, ?, ?)", (transfer_id, modality, type_uid, uid, transfer_status)
                )

    def test_new_patient_has_changes(self):
        changes = self.check_for_changes(self.plan_set)
        self.assertEqual(changes["PatientSer"], 42)
        self.assertEqual(changes["PlanSet"]["plan-1"]["RTPLAN"], {"plan-1"})
        self.assertEqual(changes["PlanSet"]["plan-1"]["RTDOSE"], {"dose-1"})
        self.assertEqual(changes["PlanSet"]["plan-1"]["CT"], set())

    def test_identical_uids_ignore_labels_order_and_do_not_mutate_input(self):
        self.add_history()
        self.plan_set["PlanSet"]["plan-1"]["RTPlanLabel"] = "new label"
        before = deepcopy(self.plan_set)
        self.assertEqual(self.check_for_changes(self.plan_set)["PlanSet"], {})
        self.assertEqual(self.plan_set, before)

    def test_new_plan_has_changes(self):
        self.add_history()
        self.plan_set["PlanSet"]["plan-2"] = {"RTPLAN": {"plan-2"}}
        changes = self.check_for_changes(self.plan_set)
        self.assertEqual(set(changes["PlanSet"]), {"plan-2"})
        self.assertEqual(changes["PlanSet"]["plan-2"]["RTPLAN"], {"plan-2"})

    def test_new_uid_in_each_modality_has_changes(self):
        self.add_history()
        for modality in export_logger_dataclass.Modality:
            with self.subTest(modality=modality):
                current = deepcopy(self.plan_set)
                current["PlanSet"]["plan-1"].setdefault(modality.value, set()).add("new")
                changes = self.check_for_changes(current)
                self.assertEqual(set(changes["PlanSet"]), {"plan-1"})
                for other in export_logger_dataclass.Modality:
                    self.assertEqual(
                        changes["PlanSet"]["plan-1"][other.value],
                        {"new"} if other == modality else set(),
                    )

    def test_history_is_combined_across_transfers(self):
        self.add_history(objects=[("RTPLAN", "SOP_INSTANCE", "plan-1")])
        self.add_history(transfer_id=2, objects=[("RTDOSE", "SOP_INSTANCE", "dose-1")])
        self.assertEqual(self.check_for_changes(self.plan_set)["PlanSet"], {})

    def test_other_patient_or_unsent_transfer_does_not_count(self):
        self.add_history(patient="43")
        self.add_history(transfer_id=2, sent=None)
        changes = self.check_for_changes(self.plan_set)
        self.assertEqual(changes["PlanSet"]["plan-1"]["RTPLAN"], {"plan-1"})
        self.assertEqual(changes["PlanSet"]["plan-1"]["RTDOSE"], {"dose-1"})

    def test_uid_under_wrong_plan_does_not_count(self):
        self.add_history(objects=[("RTPLAN", "SOP_INSTANCE", "plan-1")])
        self.add_history(transfer_id=2, plan="plan-2")
        changes = self.check_for_changes(self.plan_set)
        self.assertEqual(changes["PlanSet"]["plan-1"]["RTDOSE"], {"dose-1"})
        self.assertEqual(changes["PlanSet"]["plan-1"]["RTPLAN"], set())

    def test_ct_requires_series_uid_type(self):
        self.add_history(objects=[("CT", "SOP_INSTANCE", "ct-1")])
        self.plan_set["PlanSet"]["plan-1"] = {"CT": {"ct-1"}}
        self.assertEqual(
            self.check_for_changes(self.plan_set)["PlanSet"]["plan-1"]["CT"], {"ct-1"}
        )
        self.add_history(transfer_id=2, objects=[("CT", "SERIES_INSTANCE", "ct-1")])
        self.assertEqual(self.check_for_changes(self.plan_set)["PlanSet"], {})

    def test_wrong_modality_does_not_count(self):
        self.add_history(objects=[
            ("RTPLAN", "SOP_INSTANCE", "plan-1"),
            ("RTSTRUCT", "SOP_INSTANCE", "dose-1"),
        ])
        self.assertEqual(
            self.check_for_changes(self.plan_set)["PlanSet"]["plan-1"]["RTDOSE"],
            {"dose-1"},
        )

    def test_extra_history_and_duplicate_rows_are_ignored(self):
        self.add_history()
        self.add_history(transfer_id=2)
        self.add_history(transfer_id=3, plan="old-plan")
        self.assertEqual(self.check_for_changes(self.plan_set)["PlanSet"], {})

    def test_logged_plan_without_objects_is_recognized(self):
        self.add_history(objects=[])
        self.plan_set["PlanSet"]["plan-1"] = {}
        self.assertEqual(self.check_for_changes(self.plan_set)["PlanSet"], {})

    def test_empty_current_plan_set_has_no_additions(self):
        self.plan_set["PlanSet"] = {}
        self.assertEqual(self.check_for_changes(self.plan_set)["PlanSet"], {})

    def test_failed_and_unknown_status_objects_are_retried(self):
        self.add_history(transfer_status=0)
        self.add_history(transfer_id=2, transfer_status=None)
        changes = self.check_for_changes(self.plan_set)
        self.assertEqual(changes["PlanSet"]["plan-1"]["RTDOSE"], {"dose-1"})
        self.add_history(transfer_id=3, transfer_status=1)
        self.assertEqual(self.check_for_changes(self.plan_set)["PlanSet"], {})

    def test_current_transfer_results_survive_reference_filtering(self):
        self.plan_set["PlanSet"]["plan-1"]["TransferResults"] = {
            ("RTPLAN", "plan-1"): (1, ""),
            ("RTDOSE", "dose-1"): (0, "Transfer failed"),
        }
        changes = self.check_for_changes(self.plan_set)
        self.assertEqual(
            changes["PlanSet"]["plan-1"]["TransferResults"][("RTDOSE", "dose-1")],
            (0, "Transfer failed"),
        )

    def test_latest_failed_references_are_added_when_aria_has_no_new_uids(self):
        self.add_history()
        self.add_history(
            transfer_id=2, sent="2026-02-01", transfer_status=0,
            objects=[("RTSTRUCT", "SOP_INSTANCE", "struct-1"),
                     ("CT", "SERIES_INSTANCE", "ct-1")],
        )
        before = deepcopy(self.plan_set)
        changes = self.check_for_changes(self.plan_set)
        plan = changes["PlanSet"]["plan-1"]
        self.assertEqual(plan["RTSTRUCT"], {"struct-1"})
        self.assertEqual(plan["CT"], {"ct-1"})
        self.assertEqual(plan["RTPLAN"], set())
        self.assertEqual(plan["RTDOSE"], set())
        self.assertEqual(plan["TransferResults"], {})
        self.assertEqual(self.plan_set, before)

    def test_newer_failure_overrides_earlier_success_by_sent_dt_not_id(self):
        self.add_history(transfer_id=2, sent="2026-01-01")
        self.add_history(transfer_id=1, sent="2026-02-01", transfer_status=0)
        changes = self.check_for_changes(self.plan_set)
        self.assertEqual(changes["PlanSet"]["plan-1"]["RTPLAN"], {"plan-1"})
        self.assertEqual(changes["PlanSet"]["plan-1"]["RTDOSE"], {"dose-1"})

    def test_newer_success_prevents_retry_of_older_failed_reference(self):
        self.add_history()
        objects = [("CT", "SERIES_INSTANCE", "ct-1")]
        self.add_history(transfer_id=3, sent="2026-02-01", objects=objects, transfer_status=0)
        self.add_history(transfer_id=2, sent="2026-03-01", objects=objects)
        self.assertEqual(self.check_for_changes(self.plan_set)["PlanSet"], {})

    def test_equal_sent_dt_uses_latest_transfer_and_object_id(self):
        self.add_history(transfer_status=0)
        self.add_history(transfer_id=2)
        self.assertEqual(self.check_for_changes(self.plan_set)["PlanSet"], {})
        with self.engine.begin() as connection:
            connection.exec_driver_sql(
                "INSERT INTO DicomObject (RtPlanId, Modality, TypeUid, ReferenceUid, TransferStatus) "
                "VALUES (2, 'CT', 'SERIES_INSTANCE', 'ct-1', 0)"
            )
            connection.exec_driver_sql(
                "INSERT INTO DicomObject (RtPlanId, Modality, TypeUid, ReferenceUid, TransferStatus) "
                "VALUES (2, 'CT', 'SERIES_INSTANCE', 'ct-1', 1)"
            )
        self.assertEqual(self.check_for_changes(self.plan_set)["PlanSet"], {})

    def test_failed_references_from_other_patients_plans_or_unsent_attempts_are_excluded(self):
        self.add_history()
        objects = [("CT", "SERIES_INSTANCE", "ct-1")]
        self.add_history(transfer_id=2, patient="43", objects=objects, transfer_status=0)
        self.add_history(transfer_id=3, plan="old-plan", objects=objects, transfer_status=0)
        self.add_history(transfer_id=4, sent=None, objects=objects, transfer_status=0)
        self.assertEqual(self.check_for_changes(self.plan_set)["PlanSet"], {})

    def test_returned_collections_are_independent_and_metadata_is_preserved(self):
        self.add_history()
        self.plan_set["PatientID"] = "patient-id"
        self.plan_set["PlanSet"]["plan-1"]["RTRECORD"].add("record-1")
        before = deepcopy(self.plan_set)
        changes = self.check_for_changes(self.plan_set)
        self.assertEqual(changes["PatientID"], "patient-id")
        self.assertEqual(changes["PlanSet"]["plan-1"]["RTPlanLabel"], "label")
        changes["PlanSet"]["plan-1"]["RTRECORD"].add("record-2")
        self.assertEqual(self.plan_set, before)

    def test_discovered_references_are_filtered_again(self):
        self.add_history(objects=[
            ("RTPLAN", "SOP_INSTANCE", "plan-1"),
            ("RTSTRUCT", "SOP_INSTANCE", "struct-1"),
            ("CT", "SERIES_INSTANCE", "ct-1"),
        ])
        changes = self.check_for_changes(self.plan_set)
        changes["PlanSet"]["plan-1"]["RTSTRUCT"].add("struct-1")
        changes["PlanSet"]["plan-1"]["CT"].update({"ct-1", "ct-2"})
        filtered = self.check_for_changes(changes)
        self.assertEqual(filtered["PlanSet"]["plan-1"]["RTPLAN"], set())
        self.assertEqual(filtered["PlanSet"]["plan-1"]["RTSTRUCT"], set())
        self.assertEqual(filtered["PlanSet"]["plan-1"]["CT"], {"ct-2"})
        self.assertEqual(filtered["PlanSet"]["plan-1"]["RTDOSE"], {"dose-1"})


class ChangedObjectsForwardingTests(unittest.TestCase):
    def setUp(self):
        source = (
            Path(__file__).resolve().parents[1]
            / "module" / "Interfaces" / "conquest_dicom_interface.py"
        )
        tree = ast.parse(source.read_text(encoding="utf-8"))
        functions = [
            node for node in tree.body
            if isinstance(node, ast.FunctionDef)
            and node.name in ("c_move_to_krest_hus", "_move_objects")
        ]
        association = Mock(is_established=True)

        def move_response(*args, **kwargs):
            status = Dataset()
            status.Status = 0x0000
            return iter([(status, None)])

        association.send_c_move.side_effect = move_response
        ae = Mock()
        ae.associate.return_value = association
        namespace = {
            "AE": Mock(return_value=ae),
            "Dataset": Dataset,
            "Modality": export_logger_dataclass.Modality,
            "PatientRootQueryRetrieveInformationModelMove": "move",
            "PatientRootQueryRetrieveInformationModelFind": "find",
            "check_c_move_responses": check_c_move_responses,
            "transfer_failure": transfer_failure,
            "conquest_db_interface": Mock(),
            "config": SimpleNamespace(
                conquest_krest=SimpleNamespace(
                    dicom=SimpleNamespace(server="localhost", port=11112, aet="LOCAL")
                ),
                krest=SimpleNamespace(dicom=SimpleNamespace(aet="KREST")),
            ),
        }
        exec(compile(ast.Module(body=functions, type_ignores=[]), str(source), "exec"), namespace)
        self.forward = namespace["c_move_to_krest_hus"]
        self.association = association

    def test_only_selected_objects_are_forwarded_once(self):
        self.forward({
            "PatientSer": 42,
            "PatientID": "patient-id",
            "PlanSet": {
                "old-plan": {"RTPlanLabel": "label", "RTPLAN": set(), "RTDOSE": {"1.2.3"}, "CT": {"1.2.4"}},
                "other-plan": {"RTDOSE": {"1.2.3"}, "CT": {"1.2.4"}},
            },
        })
        calls = self.association.send_c_move.call_args_list
        self.assertEqual(len(calls), 2)
        actual = set()
        for call in calls:
            ds = call.args[0]
            actual.add((
                ds.QueryRetrieveLevel,
                str(ds.SeriesInstanceUID if ds.QueryRetrieveLevel == "SERIES" else ds.SOPInstanceUID),
            ))
            self.assertEqual(ds.PatientID, "patient-id")
            self.assertEqual(call.kwargs["move_aet"], "KREST")
        self.assertEqual(actual, {("IMAGE", "1.2.3"), ("SERIES", "1.2.4")})
        self.association.send_c_find.assert_not_called()
        self.association.release.assert_called_once()

    def test_failed_object_does_not_stop_independent_object(self):
        def response(ds, **kwargs):
            status = Dataset()
            status.Status = 0xA801 if ds.SOPInstanceUID == "1.2.3" else 0x0000
            return iter([(status, None)])

        self.association.send_c_move.side_effect = response
        plan = {"RTDOSE": {"1.2.3"}, "RTRECORD": {"1.2.4"}}
        self.forward({"PatientID": "patient-id", "PlanSet": {"plan": plan}})
        self.assertEqual(plan["TransferResults"][("RTDOSE", "1.2.3")][0], 0)
        self.assertEqual(plan["TransferResults"][("RTRECORD", "1.2.4")], (1, ""))
        self.assertEqual(self.association.send_c_move.call_count, 2)
        self.association.release.assert_called_once()

    def test_failed_plan_skips_dependents_but_other_plan_continues(self):
        def response(ds, **kwargs):
            status = Dataset()
            status.Status = 0xA801 if ds.SOPInstanceUID == "1.2.3" else 0x0000
            return iter([(status, None)])

        self.association.send_c_move.side_effect = response
        failed = {"RTPLAN": {"1.2.3"}, "RTDOSE": {"1.2.4"}}
        independent = {"RTRECORD": {"1.2.5"}}
        self.forward({
            "PatientID": "patient-id",
            "PlanSet": {"failed": failed, "other": independent},
        })
        self.assertEqual(failed["TransferResults"][("RTPLAN", "1.2.3")][0], 0)
        self.assertEqual(failed["TransferResults"][("RTDOSE", "1.2.4")][0], 0)
        self.assertIn("dependency", failed["TransferResults"][("RTDOSE", "1.2.4")][1])
        self.assertEqual(independent["TransferResults"][("RTRECORD", "1.2.5")], (1, ""))
        self.assertEqual(self.association.send_c_move.call_count, 2)

    def test_upstream_failure_is_preserved_without_retransmission(self):
        plan = {
            "RTDOSE": {"1.2.3"},
            "TransferResults": {("RTDOSE", "1.2.3"): (0, "ARIA failed")},
        }
        self.forward({"PatientID": "patient-id", "PlanSet": {"plan": plan}})
        self.association.send_c_move.assert_not_called()
        self.assertEqual(plan["TransferResults"][("RTDOSE", "1.2.3")], (0, "ARIA failed"))

    def test_association_failure_records_errors_without_raising(self):
        self.association.is_established = False
        plan = {"RTDOSE": {"1.2.3"}, "CT": {"1.2.4"}}
        self.forward({"PatientID": "patient-id", "PlanSet": {"plan": plan}})
        self.association.send_c_move.assert_not_called()
        self.assertTrue(all(result[0] == 0 for result in plan["TransferResults"].values()))


class TransferLoggingTests(unittest.TestCase):
    def test_pass_and_fail_are_persisted_without_measuring_missing_failed_files(self):
        engine = create_engine("sqlite://")
        self.addCleanup(engine.dispose)
        with engine.begin() as connection:
            connection.exec_driver_sql(
                "CREATE TABLE DicomTransfer "
                "(DicomTransferId INTEGER PRIMARY KEY, PatientSer TEXT, SentDt TEXT)"
            )
            connection.exec_driver_sql(
                "CREATE TABLE RTPlan (RtPlanId INTEGER PRIMARY KEY, DicomTransferId INTEGER, "
                "PlanSopUid TEXT, PlanLabel TEXT, Apprec TEXT)"
            )
            connection.exec_driver_sql(
                "CREATE TABLE DicomObject (DicomObjectId INTEGER PRIMARY KEY, "
                "RtPlanId INTEGER, ReferenceUid TEXT, TypeUid TEXT, Modality TEXT, "
                "BytesStored INTEGER, TransferStatus INTEGER, TransferMessage TEXT, CreatedDt TEXT)"
            )
        source = (
            Path(__file__).resolve().parents[1]
            / "module" / "Interfaces" / "export_logger_interface.py"
        )
        tree = ast.parse(source.read_text(encoding="utf-8"))
        cls = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "LogDatabase")
        method = next(node for node in cls.body if isinstance(node, ast.FunctionDef) and node.name == "add_patient")
        tools = Mock()
        tools.get_bytes_stored.return_value = 123
        conquest = Mock()
        conquest.get_sop_filenames.return_value = ["file.dcm"]
        namespace = {
            "Session": Session,
            "datetime": datetime,
            "export_logger_dataclass": export_logger_dataclass,
            "conquest_db_interface": conquest,
            "tools": tools,
            "transfer_failure": transfer_failure,
        }
        exec(compile(ast.Module(body=[method], type_ignores=[]), str(source), "exec"), namespace)
        namespace["add_patient"](SimpleNamespace(engine=engine), None, {
            "PatientSer": 42,
            "PlanSet": {"plan": {
                "RTDOSE": {"1.2.3", "1.2.4", "1.2.5"},
                "TransferResults": {
                    ("RTDOSE", "1.2.3"): (1, ""),
                    ("RTDOSE", "1.2.4"): (0, "C-MOVE: status 0xA801"),
                },
            }},
        })
        with engine.connect() as connection:
            rows = connection.exec_driver_sql(
                "SELECT ReferenceUid, TransferStatus, TransferMessage, BytesStored FROM DicomObject"
            ).all()
        actual = {uid: (passed, message, size) for uid, passed, message, size in rows}
        self.assertEqual(actual["1.2.3"], (1, "", 123))
        self.assertEqual(actual["1.2.4"], (0, "C-MOVE: status 0xA801", None))
        self.assertEqual(actual["1.2.5"], (0, "No final transfer result recorded", None))
        conquest.get_sop_filenames.assert_called_once_with("1.2.3", None)
        tools.get_bytes_stored.assert_called_once_with(["file.dcm"])


class LocalRetrievalTests(unittest.TestCase):
    def setUp(self):
        source = (
            Path(__file__).resolve().parents[1]
            / "module" / "utils" / "orchestrator.py"
        )
        tree = ast.parse(source.read_text(encoding="utf-8"))
        function = next(
            node for node in tree.body
            if isinstance(node, ast.FunctionDef) and node.name == "move_patient_to_conquest"
        )
        self.tools = Mock()
        self.conquest = Mock()
        self.forwarder = Mock()
        self.conquest.check_exists_sop.return_value = False
        self.conquest.get_rt_struct_uid.return_value = (["struct"], "label")
        self.conquest.find_referenced_ct_series.return_value = {"ct"}
        self.tools.transmit_rt_record.return_value = {"record": (1, "")}
        self.tools.transmit_rt_struct.return_value = {"struct": (1, "")}
        self.tools.transmit_ct_series.return_value = {"ct": (1, "")}
        namespace = {
            "tools": self.tools,
            "conquest_db_interface": self.conquest,
            "conquest_dicom_interface": self.forwarder,
            "export_logger_dataclass": export_logger_dataclass,
            "transfer_failure": transfer_failure,
            "check_for_changes_and_errors": lambda plan_set: plan_set,
        }
        exec(compile(ast.Module(body=[function], type_ignores=[]), str(source), "exec"), namespace)
        self.retrieve = namespace["move_patient_to_conquest"]
        self.plan = {
            "RTPLAN": {"plan"}, "RTDOSE": {"dose"}, "RTRECORD": {"record"},
            "RTSTRUCT": set(), "CT": set(),
        }

    def test_plan_failure_skips_reference_lookups_and_marks_known_objects_failed(self):
        self.tools.transmit_rt_plan_dose.return_value = {
            "plan": (0, "ARIA failed"), "dose": (1, ""),
        }
        self.retrieve({"PatientID": "patient", "PlanSet": {"plan": self.plan}})
        self.conquest.get_rt_struct_uid.assert_not_called()
        self.tools.transmit_rt_record.assert_not_called()
        self.assertTrue(all(result[0] == 0 for result in self.plan["TransferResults"].values()))
        self.assertIn("ARIA failed", self.plan["TransferResults"][("RTPLAN", "plan")][1])

    def test_dose_failure_does_not_stop_record_or_ct_retrieval(self):
        self.tools.transmit_rt_plan_dose.return_value = {
            "plan": (1, ""), "dose": (0, "Dose failed"),
        }
        self.retrieve({"PatientID": "patient", "PlanSet": {"plan": self.plan}})
        self.assertEqual(self.plan["TransferResults"][("RTDOSE", "dose")], (0, "Dose failed"))
        self.assertEqual(self.plan["TransferResults"][("RTRECORD", "record")], (1, ""))
        self.assertEqual(self.plan["TransferResults"][("CT", "ct")], (1, ""))

    def test_structure_failure_skips_known_ct_and_still_retrieves_records(self):
        self.plan["CT"] = {"ct"}
        self.tools.transmit_rt_plan_dose.return_value = {"plan": (1, ""), "dose": (1, "")}
        self.tools.transmit_rt_struct.return_value = {"struct": (0, "Structure failed")}
        self.retrieve({"PatientID": "patient", "PlanSet": {"plan": self.plan}})
        self.tools.transmit_ct_series.assert_not_called()
        self.assertEqual(self.plan["TransferResults"][("CT", "ct")][0], 0)
        self.assertEqual(self.plan["TransferResults"][("RTRECORD", "record")], (1, ""))


if __name__ == "__main__":
    unittest.main()
