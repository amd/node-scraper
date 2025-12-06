###############################################################################
#
# MIT License
#
# Copyright (c) 2025 Advanced Micro Devices, Inc.
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
#
###############################################################################
from typing import Dict, List, Optional, Set, Type, TypeVar

from pydantic import BaseModel, Field, ValidationError, field_validator

from nodescraper.enums import EventCategory, EventPriority
from nodescraper.interfaces import DataAnalyzer
from nodescraper.models import TaskResult
from nodescraper.utils import get_exception_traceback

from .analyzer_args import PcieAnalyzerArgs, normalize_to_dict
from .pcie_data import (
    BdfStr,
    CorrErrMaskReg,
    CorrErrStatReg,
    ECap16Gt,
    ECapAer,
    ECapSecpci,
    ParityMisMatchStat16GT,
    PcieCapStructure,
    PcieCfgSpace,
    PcieDataModel,
    PcieExp,
    PcieRegister,
    UncorrErrMaskReg,
    UncorrErrSevReg,
    UncorrErrStatReg,
)

T_CAP = TypeVar("T_CAP", bound=PcieCapStructure)


class PcieAnalyzerInputModel(BaseModel):
    """
    PCIeAnalyzerInputModel is a data model for validating and storing input parameters
    related to PCIe (Peripheral Component Interconnect Express) analysis.
    Attributes:
        exp_speed (int): Expected PCIe speed, Speed is the PCIe Generation, constrained to values between 1 and 5 (inclusive).
        exp_width (int): Expected PCIe width, constrained to values between 1 and 16 (inclusive).
        exp_sriov_count (Optional[int]): Optional expected count of SR-IOV (Single Root I/O Virtualization) instances.
        exp_gpu_count_override (Optional[int]): Optional override for the expected GPU count.
    """

    exp_speed: int = Field(ge=1, le=5)
    exp_width: int = Field(ge=1, le=16)
    exp_sriov_count: Optional[int] = None
    exp_gpu_count_override: Optional[int] = None
    exp_max_payload_size: Dict[int, int] = Field(default_factory=dict)
    exp_max_rd_req_size: Dict[int, int] = Field(default_factory=dict)
    exp_ten_bit_tag_req_en: Dict[int, int] = Field(default_factory=dict)

    @field_validator("exp_max_rd_req_size", "exp_max_payload_size", mode="before")
    @classmethod
    def validate_exp_max_rd_req_size(cls, v: Optional[Dict[int, int]]) -> Dict[int, int]:
        """Validates the expected maximum read request size."""
        if v is None:
            return {}
        ret_dict = v.copy()
        for key, value in v.items():
            if value >= 0 and value <= 5:
                ret_dict[key] = 128 << value  # Convert to actual size in bytes
            if value not in {128, 256, 512, 1024, 2048, 4096}:
                raise ValueError(
                    "Expected max read request size must be one of: "
                    "1, 2, 3, 4, 5, 128, 256, 512, 1024, 2048, or 4096."
                )
            if key < 0 or key > 0xFFFF:
                raise ValueError(" key must be a valid BDF (0-65535).")
        return ret_dict

    @field_validator("exp_ten_bit_tag_req_en", mode="before")
    @classmethod
    def validate_exp_ten_bit_tag_req_en(cls, v: Optional[Dict[int, int]]) -> Dict[int, int]:
        """Validates the expected 10-bit tag request enable value."""
        if v is None:
            return {}
        for key, value in v.items():
            if key < 0 or key > 0xFFFF:
                raise ValueError("Key must be a valid BDF (0-65535).")
            if value not in {0, 1}:
                raise ValueError("Expected 10-bit tag request enable must be 0 or 1.")
        return v


class PcieAnalyzer(DataAnalyzer):
    """Check PCIe Data for errors

    This calls checks the following:
    - PCIe link status for each BDF
        - This checks if the link speed and width are as expected
    - AER uncorrectable errors
        - Checks PCIe AER uncorrectable error registers UNCORR_ERR_STAT_REG and reports any errors
    - AER correctable errors
        - Checks the AERs correctable error registers CORR_ERR_STAT_REG and reports any errors
    - PCIe device status errors
        - Checks PCIe device status errors reported in fields `CORR_ERR_DET` `NON_FATAL_ERR_DET` `FATAL_ERR_DET` `UR_DET`
    - PCIe status errors
        - Checks PCIe status errors reported in fields `MSTR_DATA_PAR_ERR` `SIGNALED_TARGET_ABORT` `RCVD_TARGET_ABORT`
            `RCVD_MSTR_ABORT` `SIGNALED_SYS_ERR` `DET_PARITY_ERR`

    """

    DATA_MODEL = PcieDataModel

    GPU_BRIDGE_USP_ID = "0x1501"
    GPU_BRIDGE_DSP_ID = "0x1500"

    def validate_reg(self, bdf: str, reg: PcieRegister, log_event: bool) -> bool:
        """Ensures that the register has no error has has a value

        Parameters
        ----------
        bdf : str
            base:device:function string just used for logging
        reg : PcieRegister
            Register to validate
        log_event : bool
            Whether to log an event if the register is invalid

        Returns
        -------
        bool
            True when validate successfully, False otherwise
        """
        if reg.val is None or reg.err is not None:
            if log_event:
                self._log_event(
                    category=EventCategory.IO,
                    description="No value assgined to register or register collection resulted in error",
                    priority=EventPriority.WARNING,
                    data={"value": reg.val, "error": reg.err, "bdf": bdf},
                )
            return False
        return True

    def validate_cap(
        self,
        bdf: str,
        name: str,
        capability_structure: Optional[PcieCapStructure],
        log_event: bool = True,
    ) -> bool:
        """Ensures that the capability structure has no error and exists

        Parameters
        ----------
        bdf : str
            base:device:function string just used for logging
        capability_structure : PcieCapStructure
            Capability structure to validate

        Returns
        -------
        bool
            True when validate successfully, False otherwise
        """
        if capability_structure is None:
            if log_event:
                self._log_event(
                    category=EventCategory.IO,
                    description="No value assgined to capability a structure ",
                    data={
                        "name": name,
                        "bdf": bdf,
                    },
                    priority=EventPriority.WARNING,
                )
            return False
        null_regs = capability_structure.null_err_regs()
        if null_regs:
            if log_event:
                self._log_event(
                    category=EventCategory.IO,
                    description="Capability structure has unset registers",
                    data={
                        "name": name,
                        "bdf": bdf,
                        "capability_structure": capability_structure,
                        "null_regs": null_regs,
                    },
                    priority=EventPriority.WARNING,
                )
            return False
        return True

    def validate_cap_dict(
        self,
        pcie_cfg_space: Dict[BdfStr, PcieCfgSpace],
        cap_struct: Type[PcieCapStructure],
        log_event: bool = True,
    ) -> set[str]:
        """Validates capability structures for all BDFs in the PCIe data

        Parameters
        ----------
        pcie_data : PCIeData
            The PCIe data containing configuration space for each BDF
        cap_struct : Type[PcieCapStructure]
            The capability structure type to validate against each BDF's configuration space
        log_event : bool, optional
            Whether to log an event if a BDF does not have the specified capability structure, by default True

        Returns
        -------
        set[str]
            A set of BDFs that have the specified capability structure
        """
        bdf_without_cap_struct = set()
        for bdf, cfg_space in pcie_cfg_space.items():
            cap_struct_data = cfg_space.get_struct(cap_struct)
            if not self.validate_cap(bdf, cap_struct.__name__, cap_struct_data, False):
                bdf_without_cap_struct.add(bdf)
        if log_event and len(bdf_without_cap_struct) > 0:
            self._log_event(
                category=EventCategory.IO,
                description=f"Capability Structure {cap_struct.__name__} not found in a Cfg Space",
                priority=EventPriority.WARNING,
                data={
                    "bdf_without_pcie_exp": list(bdf_without_cap_struct),
                    "num_bdfs_with_invalid_capability_structure": len(bdf_without_cap_struct),
                    "total_bdfs": len(pcie_cfg_space),
                },
            )
        return set(pcie_cfg_space.keys()) - bdf_without_cap_struct

    def get_valid_cap_dict(
        self,
        pcie_cfg_space: Dict[BdfStr, PcieCfgSpace],
        cap_struct: Type[T_CAP],
        log_event: bool = True,
    ) -> dict[BdfStr, T_CAP]:
        """Returns a dictionary of BDFs that have the specified capability structure

        Parameters
        ----------
        pcie_data : PCIeData
            The PCIe data containing configuration space for each BDF
        cap_struct : Type[T_CAP]
            The capability structure type to validate against each BDF's configuration space
        log_event : bool, optional
            Whether to log an event if a BDF does not have the specified capability structure, by default True

        Returns
        -------
        dict[BdfStr, T_CAP]
            A dictionary of BDFs that have the specified capability structure
        """
        bdfs_with_cap = self.validate_cap_dict(pcie_cfg_space, cap_struct, log_event=log_event)
        bdf_cap_struct_dict: Dict[BdfStr, T_CAP] = {}
        for bdf, cfg_space in pcie_cfg_space.items():
            if bdf not in bdfs_with_cap:
                continue
            cap_struct_data = cfg_space.get_struct(cap_struct)
            if cap_struct_data is None:
                continue
            bdf_cap_struct_dict[bdf] = cap_struct_data

        return bdf_cap_struct_dict

    def check_link_status(
        self,
        bdf_pcie_express_dict: Dict[str, PcieExp],
        exp_speed: int = 5,
        exp_width: int = 16,
    ):
        """Checks PCIe link status for each bdf in the bdf_list and compares with the expected rate/width

        Args:
            all_bdf_cfg_space (dict[BdfStr, PcieCfgSpace]):
                dict of key bdf and value PcieCfgSpace object which contains register data
            exp_speed (int): expected link speed
            exp_width (int): expected link width

        Returns:
            None
        """
        # Key: binary bit position, value: Gen <N>
        sv_gen_speed = {
            0b000000: 0,
            0b000001: 1,
            0b000010: 2,
            0b000100: 3,
            0b001000: 4,
            0b010000: 5,
        }
        for bdf, pcie_exp in bdf_pcie_express_dict.items():
            lnk_stat_reg = pcie_exp.lnk_stat_reg
            lnk_cap_2_reg = pcie_exp.lnk_cap_2_reg
            try:
                if lnk_stat_reg.curr_lnk_speed.val == 0:
                    self._log_event(
                        category=EventCategory.IO,
                        description="Link speed vector is 0",
                        data={
                            "bdf": bdf,
                            "curr_lnk_speed": lnk_stat_reg.curr_lnk_speed.val,
                            "supported_lnk_speed_vec": lnk_cap_2_reg.supported_lnk_speed_vec.val,
                        },
                        priority=EventPriority.ERROR,
                    )
                    continue

                curr_speed = lnk_stat_reg.curr_lnk_speed.get_val()
                supported_vec = lnk_cap_2_reg.supported_lnk_speed_vec.get_val()
                if curr_speed is None or supported_vec is None:
                    continue
                sv_mask = 0b1 << (curr_speed - 1)
                link_speed = sv_gen_speed[sv_mask & supported_vec]

                if link_speed != exp_speed:
                    self._log_event(
                        category=EventCategory.IO,
                        description="Unexpected link speed detected",
                        priority=EventPriority.ERROR,
                        data={
                            "bdf": bdf,
                            "current_speed": link_speed,
                            "expected_speed": exp_speed,
                        },
                    )
                if lnk_stat_reg.neg_lnk_width.get_val() != exp_width:
                    self._log_event(
                        category=EventCategory.IO,
                        description="Unexpected link width detected",
                        priority=EventPriority.ERROR,
                        data={
                            "bdf": bdf,
                            "current_width": lnk_stat_reg.neg_lnk_width.get_val(),
                            "expected_width": exp_width,
                        },
                    )
            except Exception as e:
                self._log_event(
                    category=EventCategory.IO,
                    description="Exception occurred while checking link status",
                    priority=EventPriority.ERROR,
                    data={"exception": get_exception_traceback(e)},
                )

    def check_uncorr_aer_errors(
        self,
        bdf_ecap_aer: Dict[BdfStr, ECapAer],
    ):
        """
        Checks the following AER uncorrectable error registers
        - Uncorrectable Error Status Register
        - Uncorrectable Error Mask Register
        - Uncorrectable Error Severity Register

        Args:
            bdf_cfg_space_dict (dict[BdfStr, PcieCfgSpace]):
                dict of key bdf and value PcieCfgSpace object which contains register data
        Returns:
            None
        """
        for bdf, ecap_aer in bdf_ecap_aer.items():
            stat_reg: UncorrErrStatReg = ecap_aer.uncorr_err_stat
            mask_reg: UncorrErrMaskReg = ecap_aer.uncorr_err_mask
            sev_reg: UncorrErrSevReg = ecap_aer.uncorr_err_sev
            stat_fields = stat_reg.bit_fields
            mask_fields = mask_reg.bit_fields
            sev_fields = sev_reg.bit_fields
            # sort fields by bit position using offset
            sorted_stat_fields = sorted(stat_fields.values(), key=lambda x: x.bit_mask)
            sorted_mask_fields = sorted(mask_fields.values(), key=lambda x: x.bit_mask)
            sorted_sev_fields = sorted(sev_fields.values(), key=lambda x: x.bit_mask)
            # Iterate through all the fields in the stat, mask, and sev registers
            for stat_field, mask_field, sev_field in zip(
                sorted_stat_fields,
                sorted_mask_fields,
                sorted_sev_fields,
            ):
                pcie_field_stat_value = stat_field.get_val()
                pcie_field_mask_value = mask_field.get_val()
                pcie_field_sev_value = sev_field.get_val()
                err_descriptor: Dict[str, str] = {
                    "bdf": bdf,
                    "reg_name": stat_reg.__class__.__name__,
                    "field_desc": stat_field.desc,
                    "stat": (
                        hex(pcie_field_stat_value) if pcie_field_stat_value is not None else "None"
                    ),
                    "mask": (
                        hex(pcie_field_mask_value) if pcie_field_mask_value is not None else "None"
                    ),
                    "sev": (
                        hex(pcie_field_sev_value) if pcie_field_sev_value is not None else "None"
                    ),
                }
                if pcie_field_stat_value != 0:
                    # Error detected
                    if pcie_field_sev_value != 1:
                        if pcie_field_mask_value == 1:
                            self._log_event(
                                category=EventCategory.IO,
                                description="Masked Fatal errors were detected",
                                priority=EventPriority.ERROR,
                                data=err_descriptor,
                            )
                        else:
                            self._log_event(
                                category=EventCategory.IO,
                                description="Unmasked Fatal errors were detected",
                                priority=EventPriority.ERROR,
                                data=err_descriptor,
                            )
                    else:
                        if pcie_field_mask_value == 1:
                            self._log_event(
                                category=EventCategory.IO,
                                description="Unmasked Non-Fatal errors were detected",
                                priority=EventPriority.WARNING,
                                data=err_descriptor,
                            )
                        else:
                            self._log_event(
                                category=EventCategory.IO,
                                description="Unmasked Non-Fatal errors were detected",
                                priority=EventPriority.WARNING,
                                data=err_descriptor,
                            )

    def check_corr_aer_errors(
        self,
        bdf_ecap_aer: Dict[BdfStr, ECapAer],
    ):
        """
        Checks the following AER correctable error registers
        - Correctable Error Status Register
        - Correctable Error Mask Register

        Args:
            bdf_cfg_space_dict (dict[BdfStr, PcieCfgSpace]):
                dict of key bdf and value PcieCfgSpace object which contains register data
        Returns:
            None
        """
        for bdf, ecap_aer in bdf_ecap_aer.items():
            stat_reg: CorrErrStatReg = ecap_aer.corr_err_stat
            mask_reg: CorrErrMaskReg = ecap_aer.corr_err_mask
            stat_fields = stat_reg.bit_fields
            mask_fields = mask_reg.bit_fields
            sorted_stat_fields = sorted(stat_fields.values(), key=lambda x: x.bit_mask)
            sorted_mask_fields = sorted(mask_fields.values(), key=lambda x: x.bit_mask)

            for stat_field, mask_field in zip(
                sorted_stat_fields,
                sorted_mask_fields,
            ):
                stat_val = stat_field.get_val()
                if stat_val is not None and stat_val != 0:
                    err_dict = {
                        "bdf": bdf,
                        "reg_description": stat_reg.desc,
                        "field_description": stat_field.desc,
                        "bit_field_val": hex(stat_val),
                    }
                    if mask_field.get_val() == 1:
                        self._log_event(
                            category=EventCategory.IO,
                            description="Masked Correctable errors were detected",
                            priority=EventPriority.WARNING,
                            data=err_dict,
                        )
                    else:
                        self._log_event(
                            category=EventCategory.IO,
                            description="Masked Correctable errors were detected",
                            priority=EventPriority.ERROR,
                            data=err_dict,
                        )

    def check_pcie_device_status_errors(self, bdf_pcie_express_dict: Dict[str, PcieExp]):
        """
        Checks PCIe baseline error reported in Device Status Register
        Reference: 9.4.1 Baseline Error Reporting

        Args:
            bdf_cfg_space_dict (dict[BdfStr, PcieCfgSpace]):
                dict of key bdf and value PcieCfgSpace object which contains register data
        Returns:
            None
        """
        for bdf, pcie_exp_cap in bdf_pcie_express_dict.items():
            err_list = []
            dev_stat_reg = pcie_exp_cap.dev_stat_reg
            bit_field_list = [
                dev_stat_reg.corr_err_det,
                dev_stat_reg.non_fatal_err_det,
                dev_stat_reg.fatal_err_det,
                dev_stat_reg.ur_det,
            ]
            err_list = [bit_field for bit_field in bit_field_list if bit_field.get_val() != 0]

            if len(err_list) > 0:
                self._log_event(
                    category=EventCategory.IO,
                    description="Device Status errors were detected",
                    priority=EventPriority.WARNING,
                    data={
                        "bdf": bdf,
                        "reg_description": dev_stat_reg.desc,
                        "field_desc_list": [err.desc for err in err_list],
                        "err_bitmask_list": [err.bit_mask for err in err_list],
                        "register_value": dev_stat_reg.val,
                    },
                )

    def check_pcie_status_errors(self, bdf_cfg_space_dict: Dict[BdfStr, PcieCfgSpace]):
        """
        Checks PCIe baseline error reported in Status Registe
        Reference: 9.4.1 Baseline Error Reporting

        Args:
            bdf_cfg_space_dict (dict[BdfStr, PcieCfgSpace]):
                dict of key bdf and value PcieCfgSpace object which contains register data
        Returns:
            None
        """
        for bdf, cfg_space in bdf_cfg_space_dict.items():
            err_list = []
            stat_reg = cfg_space.type_0_configuration.status
            bit_field_list = [
                stat_reg.mstr_data_par_err,
                stat_reg.signaled_target_abort,
                stat_reg.rcvd_target_abort,
                stat_reg.rcvd_mstr_abort,
                stat_reg.signaled_sys_err,
                stat_reg.det_parity_err,
            ]
            err_list = [bit_field for bit_field in bit_field_list if bit_field.get_val() != 0]

            if len(err_list) > 0:
                self._log_event(
                    category=EventCategory.IO,
                    description="PCI Express Status register errors were detected",
                    priority=EventPriority.WARNING,
                    data={
                        "bdf": bdf,
                        "reg_description": stat_reg.desc,
                        "field_desc_list": [err.desc for err in err_list],
                        "err_bitmask_list": [err.bit_mask for err in err_list],
                        "register_value": stat_reg.val,
                    },
                )

    def check_pcie_dev_ctrl_reg(
        self,
        bdf_pcie_express_dict: Dict[str, PcieExp],
        exp_max_payload_size: Optional[int],
        exp_max_rd_req_size: Optional[int],
    ):
        """Checks 7.5.3.4 Device Control Register (Offset 08h) fields for expected value:
        - Max Payload Size
        - Max Read Request Size

        Args:
            bdf_cfg_space_dict (dict[BdfStr, PcieCfgSpace]):
                dict of key bdf and value PcieCfgSpace object which contains register data
            exp_max_payload_size (Optional[int]): expected max payload size, when None it is not checked
            exp_max_rd_req_size (Optional[int]): expected max read request size, when None it is not checked
        Returns:
            None
        """
        encoding = {
            0b000: 128,
            0b001: 256,
            0b010: 512,
            0b011: 1024,
            0b100: 2048,
            0b101: 4096,
        }
        for bdf, pcie_exp in bdf_pcie_express_dict.items():
            dev_ctrl_reg = pcie_exp.dev_ctrl_reg
            mps_val = dev_ctrl_reg.mps.get_val()
            if mps_val is None:
                continue
            max_payload_size = encoding[mps_val]
            if exp_max_payload_size is not None and max_payload_size != exp_max_payload_size:
                self._log_event(
                    category=EventCategory.IO,
                    description="Unexpected Max Payload Size detected",
                    priority=EventPriority.ERROR,
                    data={
                        "bdf": bdf,
                        "current_max_payload_size": max_payload_size,
                        "expected_max_payload_size": exp_max_payload_size,
                    },
                )

            max_rd_req_val = dev_ctrl_reg.max_rd_req_size.get_val()
            if max_rd_req_val is None:
                continue
            max_rd_req_size = encoding[max_rd_req_val]
            if max_rd_req_size is not None and max_rd_req_size != exp_max_rd_req_size:
                self._log_event(
                    category=EventCategory.IO,
                    description="Unexpected Max Read Request Size detected",
                    priority=EventPriority.ERROR,
                    data={
                        "bdf": bdf,
                        "current_max_rd_req_size": max_rd_req_size,
                        "expected_max_rd_req_size": exp_max_rd_req_size,
                    },
                )

    def check_pcie_dev_ctrl_2_reg(
        self,
        bdf_pcie_express_dict: Dict[str, PcieExp],
        exp_ten_bit_tag_req_en: Optional[int],
    ):
        """Checks 7.5.3.16 Device Control 2 Register (Offset 28h) fields for expected value:
        - 10-bit Tag Request Enable

        Args:
            bdf_cfg_space_dict (dict[BdfStr, PcieCfgSpace]):
                dict of key bdf and value PcieCfgSpace object which contains register data
            exp_ten_bit_tag_req_en (Optional[int]): expected 10-bit tag request enable, when None it is not checked
        Returns:
            None
        """
        for bdf, pcie_exp in bdf_pcie_express_dict.items():
            dev_ctrl_2_reg = pcie_exp.dev_ctrl_2_reg
            ten_bit_tag_req_en = dev_ctrl_2_reg.ten_bit_tag_req_en.get_val()
            if exp_ten_bit_tag_req_en is not None and ten_bit_tag_req_en != exp_ten_bit_tag_req_en:
                self._log_event(
                    category=EventCategory.IO,
                    description="Unexpected 10-bit Tag Request Enable detected",
                    priority=EventPriority.ERROR,
                    data={
                        "bdf": bdf,
                        "current_ten_bit_tag_req_en": ten_bit_tag_req_en,
                        "expected_ten_bit_tag_req_en": exp_ten_bit_tag_req_en,
                    },
                )

    def instantaneous_par_err_chk(self, bdf_cfg_space_dict: Dict[str, ECap16Gt]):
        """Instantaneous parity error check for ECap16Gt registers, will
        log an event if any lanes have parity errors.

        Parameters
        ----------
        bdf_cfg_space_dict : Dict[str, ECap16Gt]
            Dictionary of BDFs and their corresponding ECap16Gt capability structure
        """
        for bdf, ecap_pl_16gt in bdf_cfg_space_dict.items():
            par_mismatch_stat: ParityMisMatchStat16GT = ecap_pl_16gt.parity_mismatch_stat
            retimer_fst_par_mismatch_stat = ecap_pl_16gt.retimer_fst_parity_mismatch_stat
            for parity_register in [
                par_mismatch_stat,
                retimer_fst_par_mismatch_stat,
            ]:
                if parity_register.val is None:
                    continue
                par_bad_lanes = [
                    1 if (parity_register.val >> bit) & 1 else 0 for bit in range(0, 32)
                ]
                number_of_bad_lanes = sum(par_bad_lanes)
                if number_of_bad_lanes > 0:
                    self._log_event(
                        category=EventCategory.IO,
                        description="Lanes have parity errors",
                        priority=EventPriority.ERROR,
                        data={
                            "bdf": bdf,
                            "reg_name": parity_register.__class__.__name__,
                            "reg_desc": parity_register.desc,
                            "register_value": parity_register.val,
                            "number_of_bad_lanes": number_of_bad_lanes,
                        },
                    )

    def lane_error_status_chk(self, ecap_sec_pci_dict: Dict[str, ECapSecpci]):
        """Lane error status check for ECapSecpci registers, will log an event if any lanes have errors.

        Parameters
        ----------
        ecap_sec_pci_dict : Dict[str, ECapSecpci]
            Dictionary of BDFs and their corresponding ECapSecpci capability structure
        """
        for bdf, ecap_sec_pci in ecap_sec_pci_dict.items():
            lane_error_stat = ecap_sec_pci.lane_err_stat
            lane_error_stat_val = lane_error_stat.val
            if lane_error_stat_val != 0:
                self._log_event(
                    category=EventCategory.IO,
                    description="Lane error detected",
                    priority=EventPriority.ERROR,
                    data={
                        "bdf": bdf,
                        "reg_name": lane_error_stat.__class__.__name__,
                        "register_value": lane_error_stat_val,
                    },
                )

    def device_consistancy_chk(self, bdf_cfg_space_dict: Dict[BdfStr, PcieCfgSpace]):
        """Checks that the configurable fields in the PCIe devices are all consistent"""
        # Build a dynamic map of device IDs to BDFs from the actual devices in the system
        dev_id_bdf_map: Dict[int, List[BdfStr]] = {}

        for bdf, cfg_space in bdf_cfg_space_dict.items():
            # Collect Unique device Ids contained in this system
            device_id = cfg_space.type_0_configuration.device_id.val
            if device_id is None:
                self._log_event(
                    category=EventCategory.IO,
                    description="No value assigned to device id, unable to check consistency due to missing data",
                    data={
                        "bdf": bdf,
                    },
                    priority=EventPriority.WARNING,
                )
                continue

            # Dynamically add device IDs as we encounter them
            if device_id not in dev_id_bdf_map:
                dev_id_bdf_map[device_id] = []
            dev_id_bdf_map[device_id].append(bdf)

        # check the values are all equal for select registers
        cap_struct_dict = self.get_valid_cap_dict(bdf_cfg_space_dict, PcieExp, log_event=False)
        for collected_device_id, list_of_bdfs in dev_id_bdf_map.items():
            # check the values are all equal for select registers
            mps = []
            mrs = []
            tbt = []
            log_event = False
            for bdf in list_of_bdfs:
                if bdf not in cap_struct_dict:
                    # Missing Capability structure for this BDF, skip it, log event at end
                    log_event = True
                    continue
                pcie_exp = cap_struct_dict[bdf]
                dev_ctrl_reg = pcie_exp.dev_ctrl_reg
                mps.append(dev_ctrl_reg.mps.val)
                mrs.append(dev_ctrl_reg.max_rd_req_size.val)
                tbt.append(dev_ctrl_reg.ext_tag_field_en.val)
            # check the values are all equal for select registers
            if len(set(mps)) > 1 or len(set(mrs)) > 1 or len(set(tbt)) > 1 or log_event:
                collected_device_id_str = hex(collected_device_id)
                self._log_event(
                    category=EventCategory.IO,
                    description=f"PCIe device {collected_device_id_str} has inconsistent values",
                    priority=EventPriority.WARNING,
                    data={
                        "dev_id": collected_device_id_str,
                        "bdf_list": list_of_bdfs,
                        "max_payload_size_list": mps,
                        "max_rd_req_size_list": mrs,
                        "ext_tag_field_en_list": tbt,
                    },
                )

    def check_ecap_16gt_regs(
        self,
        bdf_cfg_space_dict: dict[BdfStr, PcieCfgSpace],
    ):
        """Acquires ECap16Gt capability structure and checks for instantaneous parity errors"""
        CAP_STRUCTURE = ECap16Gt
        bdf_ecap_16gt_dict = self.get_valid_cap_dict(
            bdf_cfg_space_dict, CAP_STRUCTURE, log_event=True
        )
        self.instantaneous_par_err_chk(bdf_cfg_space_dict=bdf_ecap_16gt_dict)

    def check_ecap_sec_pci_regs(
        self,
        bdf_cfg_space_dict: dict[BdfStr, PcieCfgSpace],
    ):
        """Acquires ECapSecpci capability structure and checks for lane errors"""
        CAP_STRUCTURE = ECapSecpci
        bdf_ecap_secondary_pci = self.get_valid_cap_dict(
            bdf_cfg_space_dict, CAP_STRUCTURE, log_event=True
        )
        self.lane_error_status_chk(ecap_sec_pci_dict=bdf_ecap_secondary_pci)

    def check_ecap_aer_errors(
        self,
        bdf_cfg_space_dict: dict[BdfStr, PcieCfgSpace],
    ):
        """Acquires ECapAer capability structure and checks for AER errors"""
        CAP_STRUCTURE = ECapAer
        bdf_ecap_aer_error = self.get_valid_cap_dict(
            bdf_cfg_space_dict, CAP_STRUCTURE, log_event=True
        )
        self.check_uncorr_aer_errors(bdf_ecap_aer=bdf_ecap_aer_error)
        self.check_corr_aer_errors(bdf_ecap_aer=bdf_ecap_aer_error)

    def check_pcie_exp_capability_structure_errors(
        self, bdf_cfg_space_dict: Dict[BdfStr, PcieCfgSpace]
    ):
        """Checks the PCIe Express capability structure for errors"""
        CAP_STRUCTURE = PcieExp
        bdf_pcie_express_dict = self.get_valid_cap_dict(
            bdf_cfg_space_dict, CAP_STRUCTURE, log_event=False
        )
        self.check_pcie_device_status_errors(bdf_pcie_express_dict=bdf_pcie_express_dict)

    def check_pcie_exp_capability_structure_config(
        self,
        bdf_cfg_space_dict: dict[BdfStr, PcieCfgSpace],
        exp_max_payload_size: Optional[int] = None,
        exp_max_rd_req_size: Optional[int] = None,
        exp_ten_bit_tag_req_en: Optional[int] = None,
    ):
        """Checks the PCIe Express capability structure for errors"""
        CAP_STRUCTURE = PcieExp

        bdf_pcie_express_dict = self.get_valid_cap_dict(
            bdf_cfg_space_dict, CAP_STRUCTURE, log_event=True
        )

        if exp_max_payload_size is not None or exp_max_rd_req_size is not None:
            self.check_pcie_dev_ctrl_reg(
                bdf_pcie_express_dict=bdf_pcie_express_dict,
                exp_max_payload_size=exp_max_payload_size,
                exp_max_rd_req_size=exp_max_rd_req_size,
            )

        if exp_ten_bit_tag_req_en is not None:
            self.check_pcie_dev_ctrl_2_reg(
                bdf_pcie_express_dict=bdf_pcie_express_dict,
                exp_ten_bit_tag_req_en=exp_ten_bit_tag_req_en,
            )

    @staticmethod
    def filter_pcie_data_by_device_id(
        bdf_cfg_space_dict: Dict[BdfStr, PcieCfgSpace],
        device_ids: Set[int],
    ) -> Dict[BdfStr, PcieCfgSpace]:
        """Filters the PCIe data by device ID

        Parameters
        ----------
        device_ids : set[int]
            Set of device IDs to filter by

        Returns
        -------
        Dict[BdfStr, PcieCfgSpace]
            Dictionary of BDFs and their corresponding PCIe configuration space
        """
        new_cfg_space_dict: Dict[BdfStr, PcieCfgSpace] = {}
        for bdf, pcie_data in bdf_cfg_space_dict.items():
            dev_id = pcie_data.type_0_configuration.device_id.val
            if dev_id in device_ids:
                new_cfg_space_dict[bdf] = pcie_data
        return new_cfg_space_dict

    def check_gpu_count(
        self,
        pcie_data: PcieDataModel,
        expected_gpu_count: Optional[int] = None,
    ):
        """Check if GPU count from PCIe data matches expected count

        Parameters
        ----------
        pcie_data : PcieDataModel
            PCIe data model containing collected PCIe configuration space data
        expected_gpu_count : Optional[int], optional
            Expected GPU count, by default None (no check performed)
        """
        if expected_gpu_count is None:
            return

        gpu_count_from_pcie = 0
        for cfg_space in pcie_data.pcie_cfg_space.values():
            vendor_id = cfg_space.type_0_configuration.vendor_id.val
            if vendor_id == self.system_info.vendorid_ep:
                gpu_count_from_pcie += 1

        if gpu_count_from_pcie != expected_gpu_count:
            self._log_event(
                category=EventCategory.IO,
                description="GPU count mismatch",
                priority=EventPriority.ERROR,
                data={
                    "gpu_count_from_pcie": gpu_count_from_pcie,
                    "expected_gpu_count": expected_gpu_count,
                },
            )
        else:
            self._log_event(
                category=EventCategory.IO,
                description="GPU count matches expected",
                priority=EventPriority.INFO,
                data={
                    "gpu_count": gpu_count_from_pcie,
                },
            )

    def analyze_data(
        self, data: PcieDataModel, args: Optional[PcieAnalyzerArgs] = None
    ) -> TaskResult:
        """Check PCIe data for errors by analyzing the PCIe register space and
        checking the enumeration of the GPUs and optional SR-IOV VFs

        Parameters
        ----------
        data : PcieDataModel
            PCIe data model containing collected PCIe configuration space data
        args : Optional[PcieAnalyzerArgs], optional
            Analyzer arguments containing expected values for validation, by default None

        Returns
        -------
        TaskResult
            Result of the analysis
        """
        if args is None:
            args = PcieAnalyzerArgs()

        exp_speed = args.exp_speed
        exp_width = args.exp_width
        exp_sriov_count = args.exp_sriov_count
        exp_gpu_count_override = args.exp_gpu_count_override
        exp_max_payload_size = normalize_to_dict(
            args.exp_max_payload_size, self.system_info.vendorid_ep
        )
        exp_max_rd_req_size = normalize_to_dict(
            args.exp_max_rd_req_size, self.system_info.vendorid_ep
        )
        exp_ten_bit_tag_req_en = normalize_to_dict(
            args.exp_ten_bit_tag_req_en, self.system_info.vendorid_ep
        )
        try:
            pcie_input_data = PcieAnalyzerInputModel(
                exp_speed=exp_speed,
                exp_width=exp_width,
                exp_sriov_count=exp_sriov_count,
                exp_gpu_count_override=exp_gpu_count_override,
                exp_ten_bit_tag_req_en=exp_ten_bit_tag_req_en,
                exp_max_payload_size=exp_max_payload_size,
                exp_max_rd_req_size=exp_max_rd_req_size,
            )
        except ValidationError as val_error:
            self._log_event(
                category=EventCategory.RUNTIME,
                description="User input for PcieAnalyzerModel is invalid",
                priority=EventPriority.ERROR,
                data={
                    "validation_error": get_exception_traceback(val_error),
                    "valid_input": {
                        "exp_speed": "int, 1-5",
                        "exp_width": "int, 1-16",
                        "exp_sriov_count": "Optional[int]",
                        "exp_gpu_count_override": "Optional[int]",
                    },
                    "actual_input": {
                        "exp_speed": exp_speed,
                        "exp_width": exp_width,
                        "exp_sriov_count": exp_sriov_count,
                        "exp_gpu_count_override": exp_gpu_count_override,
                    },
                },
            )
            return self.result

        pcie_data: PcieDataModel = data

        if pcie_data.pcie_cfg_space == {} and pcie_data.vf_pcie_cfg_space == {}:
            # If both of the PCIe Configuration spaces are
            self._log_event(
                category=EventCategory.IO,
                description="No PCIe config space found",
                priority=EventPriority.WARNING,
            )
            return self.result

        # Check every link in the PCIe configuration space for the expected capability structure,
        # but don't check VF since those will be 0
        bdf_pcie_express_dict = self.get_valid_cap_dict(
            pcie_data.pcie_cfg_space,
            PcieExp,
            log_event=True,
        )
        self.check_link_status(
            bdf_pcie_express_dict=bdf_pcie_express_dict,
            exp_speed=exp_speed,
            exp_width=exp_width,
        )

        amd_device_ids = set()
        for cfg_space in pcie_data.pcie_cfg_space.values():
            vendor_id = cfg_space.type_0_configuration.vendor_id.val
            device_id = cfg_space.type_0_configuration.device_id.val
            if vendor_id == self.system_info.vendorid_ep and device_id is not None:
                amd_device_ids.add(device_id)

        # Filter PCIe data for AMD GPUs
        oam_pcie_data = self.filter_pcie_data_by_device_id(
            bdf_cfg_space_dict=pcie_data.pcie_cfg_space,
            device_ids=amd_device_ids,
        )

        amd_vf_device_ids = set()
        if pcie_data.vf_pcie_cfg_space is not None:
            for cfg_space in pcie_data.vf_pcie_cfg_space.values():
                vendor_id = cfg_space.type_0_configuration.vendor_id.val
                device_id = cfg_space.type_0_configuration.device_id.val
                if vendor_id == self.system_info.vendorid_ep and device_id is not None:
                    amd_vf_device_ids.add(device_id)

            oam_vf_pcie_data = self.filter_pcie_data_by_device_id(
                bdf_cfg_space_dict=pcie_data.vf_pcie_cfg_space,
                device_ids=amd_vf_device_ids,
            )
        else:
            oam_vf_pcie_data = {}

        # Include bridge/retimer devices (0x1500, 0x1501)
        us_ds_retimer = self.filter_pcie_data_by_device_id(
            bdf_cfg_space_dict=pcie_data.pcie_cfg_space,
            device_ids={0x1500, 0x1501},
        )
        ubb_data = {**oam_pcie_data, **us_ds_retimer}
        ubb_data_with_vf = {**ubb_data, **oam_vf_pcie_data}
        # Type 0 Configuration Space Checks
        self.check_pcie_status_errors(bdf_cfg_space_dict=ubb_data_with_vf)
        # Check other capability structures
        dev_ids = set(
            list(pcie_input_data.exp_max_payload_size.keys())
            + list(pcie_input_data.exp_max_rd_req_size.keys())
            + list(pcie_input_data.exp_ten_bit_tag_req_en.keys())
        )
        for device_id_to_check in dev_ids:
            cfg_space_filtered = self.filter_pcie_data_by_device_id(
                bdf_cfg_space_dict=pcie_data.pcie_cfg_space,
                device_ids={device_id_to_check},
            )
            self.check_pcie_exp_capability_structure_config(
                cfg_space_filtered,
                pcie_input_data.exp_max_payload_size.get(device_id_to_check),
                pcie_input_data.exp_max_rd_req_size.get(device_id_to_check),
                pcie_input_data.exp_ten_bit_tag_req_en.get(device_id_to_check),
            )

        # run with vfs for AERs and PCIe EXP errors
        self.check_pcie_exp_capability_structure_errors(bdf_cfg_space_dict=ubb_data_with_vf)
        self.check_ecap_aer_errors(bdf_cfg_space_dict=ubb_data_with_vf)
        self.check_ecap_16gt_regs(bdf_cfg_space_dict=ubb_data)
        self.check_ecap_sec_pci_regs(bdf_cfg_space_dict=ubb_data)

        if amd_device_ids:
            self.device_consistancy_chk(
                bdf_cfg_space_dict=ubb_data,
            )
        else:
            self._log_event(
                category=EventCategory.RUNTIME,
                description="No AMD GPU devices found, skipping device consistency check",
                priority=EventPriority.INFO,
            )

        self.check_gpu_count(pcie_data, exp_gpu_count_override)

        return self.result
