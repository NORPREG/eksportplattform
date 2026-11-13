import os
import logging

from config import Config
config = Config()

from module.Interfaces import (
	aria_dicom_interface,
	conquest_db_interface,
)
from module.utils.dicom_status import transfer_failure

logger = logging.getLogger(__name__)

def transmit_ct_series(plan_root):
    return _transmit_uids(
        {uid: conquest_db_interface.check_exists_series(uid) for uid in plan_root["CT"]},
        is_series=True,
    )

def transmit_rt_struct(structure_set_uids):
    return _transmit_uids(
        {uid: conquest_db_interface.check_exists_sop(uid) for uid in structure_set_uids}
    )

def transmit_rt_plan_dose(uids_exist):
    return _transmit_uids(uids_exist)

def transmit_rt_record(rtrecord_uids):
    return transmit_rt_struct(rtrecord_uids)

def _transmit_uids(uids_exist, is_series=False):
    results = {uid: (1, "") for uid, exists in uids_exist.items() if exists}
    missing = [uid for uid, exists in uids_exist.items() if not exists]
    if not missing:
        return results
    try:
        assoc = aria_dicom_interface.get_assoc()
    except (RuntimeError, OSError) as exc:
        failure = transfer_failure(f"ARIA association failed: {exc}")
        return {**results, **{uid: failure for uid in missing}}
    try:
        for uid in missing:
            try:
                move = aria_dicom_interface.c_move_series if is_series else aria_dicom_interface.c_move_image
                results[uid] = move(assoc, uid)
            except (RuntimeError, OSError, ValueError) as exc:
                results[uid] = transfer_failure(f"ARIA transfer failed: {exc}")
    finally:
        assoc.release()
    return results

def md5hash(filename):
	import hashlib

	hash_md5 = hashlib.md5()
	with open(filename, "rb") as f:
		for chunk in iter(lambda: f.read(4096), b""):
			hash_md5.update(chunk)
	return hash_md5.hexdigest()

def get_bytes_stored(filenames, append_root=True):
	size = 0
	for filename in filenames:
		if filename:
			if append_root:
				size += os.path.getsize(config.conquest_aria.root_dir + filename)
			else:
				size += os.path.getsize(filename)

	return size