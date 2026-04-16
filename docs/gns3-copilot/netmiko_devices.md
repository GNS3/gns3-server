<!--
SPDX-License-Identifier: CC-BY-SA-4.0
See LICENSE file for licensing information.
-->

# Netmiko Supported Devices

**Netmiko Version:** 4.6.0
**Generated:** 2026-03-14 13:10:00
**Last Updated:** 2026-03-14 (Added VPCS support)

---

## Summary

- **Total Device Types:** 366
- **SSH Devices:** 154
- **Telnet Devices:** 55
- **Custom Devices:** 3

## Custom GNS3 Drivers

GNS3-Copilot includes custom Netmiko drivers optimized for GNS3 emulation:

| Platform | Device Type | Description |
|----------|-------------|-------------|
| Huawei CE | `gns3_huawei_telnet_ce` | Huawei CloudEngine driver with no authentication |
| Ruijie | `gns3_ruijie_telnet` | Ruijie OS enhanced driver with interactive command handling |
| VPCS | `gns3_vpcs_telnet` | VPCS simulator driver with ANSI code stripping |

## SSH Supported Devices

| Platform | Device Type | Source |
|----------|-------------|--------|
| A10 | `a10_ssh` | Netmiko |
| Accedian | `accedian_ssh` | Netmiko |
| Adtran | `adtran_os_ssh` | Netmiko |
| Adva | `adva_fsp150f2_ssh` | Netmiko |
| Adva | `adva_fsp150f3_ssh` | Netmiko |
| Alaxala | `alaxala_ax26s_ssh` | Netmiko |
| Alaxala | `alaxala_ax36s_ssh` | Netmiko |
| Alcatel | `alcatel_aos_ssh` | Netmiko |
| Alcatel | `alcatel_sros_ssh` | Netmiko |
| Allied | `allied_telesis_awplus_ssh` | Netmiko |
| Apresia | `apresia_aeos_ssh` | Netmiko |
| Arista | `arista_eos_ssh` | Netmiko |
| Arris | `arris_cer_ssh` | Netmiko |
| Aruba | `aruba_aoscx_ssh` | Netmiko |
| Aruba | `aruba_os_ssh` | Netmiko |
| Aruba | `aruba_osswitch_ssh` | Netmiko |
| Aruba | `aruba_procurve_ssh` | Netmiko |
| Asterfusion | `asterfusion_asternos_ssh` | Netmiko |
| Audiocode | `audiocode_66_ssh` | Netmiko |
| Audiocode | `audiocode_72_ssh` | Netmiko |
| Audiocode | `audiocode_shell_ssh` | Netmiko |
| Avaya | `avaya_ers_ssh` | Netmiko |
| Avaya | `avaya_vsp_ssh` | Netmiko |
| Bintec | `bintec_boss_ssh` | Netmiko |
| Broadcom | `broadcom_icos_ssh` | Netmiko |
| Brocade | `brocade_fastiron_ssh` | Netmiko |
| Brocade | `brocade_fos_ssh` | Netmiko |
| Brocade | `brocade_netiron_ssh` | Netmiko |
| Brocade | `brocade_nos_ssh` | Netmiko |
| Brocade | `brocade_vdx_ssh` | Netmiko |
| Brocade | `brocade_vyos_ssh` | Netmiko |
| Calix | `calix_b6_ssh` | Netmiko |
| Casa | `casa_cmts_ssh` | Netmiko |
| Cdot | `cdot_cros_ssh` | Netmiko |
| Centec | `centec_os_ssh` | Netmiko |
| Check Point | `checkpoint_gaia_ssh` | Netmiko |
| Ciena | `ciena_saos10_ssh` | Netmiko |
| Ciena | `ciena_saos_ssh` | Netmiko |
| Ciena | `ciena_waveserver_ssh` | Netmiko |
| Cisco | `cisco_apic_ssh` | Netmiko |
| Cisco | `cisco_asa_ssh` | Netmiko |
| Cisco | `cisco_ftd_ssh` | Netmiko |
| Cisco | `cisco_ios_ssh` | Netmiko |
| Cisco | `cisco_nxos_ssh` | Netmiko |
| Cisco | `cisco_s200_ssh` | Netmiko |
| Cisco | `cisco_s300_ssh` | Netmiko |
| Cisco | `cisco_tp_ssh` | Netmiko |
| Cisco | `cisco_viptela_ssh` | Netmiko |
| Cisco | `cisco_wlc_ssh` | Netmiko |
| Cisco | `cisco_xe_ssh` | Netmiko |
| Cisco | `cisco_xr_ssh` | Netmiko |
| Cloudgenix | `cloudgenix_ion_ssh` | Netmiko |
| Corelight | `corelight_linux_ssh` | Netmiko |
| Coriant | `coriant_ssh` | Netmiko |
| Cumulus | `cumulus_linux_ssh` | Netmiko |
| Dell | `dell_dnos9_ssh` | Netmiko |
| Dell | `dell_force10_ssh` | Netmiko |
| Dell | `dell_isilon_ssh` | Netmiko |
| Dell | `dell_os10_ssh` | Netmiko |
| Dell | `dell_os6_ssh` | Netmiko |
| Dell | `dell_os9_ssh` | Netmiko |
| Dell | `dell_powerconnect_ssh` | Netmiko |
| Dell | `dell_sonic_ssh` | Netmiko |
| Digi | `digi_transport_ssh` | Netmiko |
| Dlink | `dlink_ds_ssh` | Netmiko |
| Edgecore | `edgecore_sonic_ssh` | Netmiko |
| Ekinops | `ekinops_ek360_ssh` | Netmiko |
| Eltex | `eltex_esr_ssh` | Netmiko |
| Eltex | `eltex_ssh` | Netmiko |
| Endace | `endace_ssh` | Netmiko |
| Enterasys | `enterasys_ssh` | Netmiko |
| Ericsson | `ericsson_ipos_ssh` | Netmiko |
| Ericsson | `ericsson_mltn63_ssh` | Netmiko |
| Ericsson | `ericsson_mltn66_ssh` | Netmiko |
| Extreme | `extreme_ers_ssh` | Netmiko |
| Extreme | `extreme_exos_ssh` | Netmiko |
| Extreme | `extreme_netiron_ssh` | Netmiko |
| Extreme | `extreme_nos_ssh` | Netmiko |
| Extreme | `extreme_slx_ssh` | Netmiko |
| Extreme | `extreme_ssh` | Netmiko |
| Extreme | `extreme_tierra_ssh` | Netmiko |
| Extreme | `extreme_vdx_ssh` | Netmiko |
| Extreme | `extreme_vsp_ssh` | Netmiko |
| Extreme | `extreme_wing_ssh` | Netmiko |
| F5 | `f5_linux_ssh` | Netmiko |
| F5 | `f5_ltm_ssh` | Netmiko |
| F5 | `f5_tmsh_ssh` | Netmiko |
| Fiberstore | `fiberstore_fsos_ssh` | Netmiko |
| Fiberstore | `fiberstore_fsosv2_ssh` | Netmiko |
| Fiberstore | `fiberstore_networkos_ssh` | Netmiko |
| Flexvnf | `flexvnf_ssh` | Netmiko |
| Fortinet | `fortinet_ssh` | Netmiko |
| Garderos | `garderos_grs_ssh` | Netmiko |
| Generic | `generic_ssh` | Netmiko |
| Generic | `generic_termserver_ssh` | Netmiko |
| H3C (华三) | `h3c_comware_ssh` | Netmiko |
| HP | `hp_comware_ssh` | Netmiko |
| HP | `hp_procurve_ssh` | Netmiko |
| Hillstone | `hillstone_stoneos_ssh` | Netmiko |
| Huawei | `huawei_olt_ssh` | Netmiko |
| Huawei | `huawei_smartax_ssh` | Netmiko |
| Huawei | `huawei_smartaxmmi_ssh` | Netmiko |
| Huawei | `huawei_ssh` | Netmiko |
| Huawei | `huawei_vrp_ssh` | Netmiko |
| Huawei | `huawei_vrpv8_ssh` | Netmiko |
| Infinera | `infinera_packet_ssh` | Netmiko |
| Ipinfusion | `ipinfusion_ocnos_ssh` | Netmiko |
| Juniper | `juniper_junos_ssh` | Netmiko |
| Juniper | `juniper_screenos_ssh` | Netmiko |
| Juniper | `juniper_ssh` | Netmiko |
| Keymile | `keymile_nos_ssh` | Netmiko |
| Keymile | `keymile_ssh` | Netmiko |
| Lancom | `lancom_lcossx4_ssh` | Netmiko |
| Linux | `linux_ssh` | Netmiko |
| Maipu (迈普) | `maipu_ssh` | Netmiko |
| Mellanox | `mellanox_mlnxos_ssh` | Netmiko |
| Mellanox | `mellanox_ssh` | Netmiko |
| Mikrotik | `mikrotik_routeros_ssh` | Netmiko |
| Mikrotik | `mikrotik_switchos_ssh` | Netmiko |
| Mrv | `mrv_lx_ssh` | Netmiko |
| Mrv | `mrv_optiswitch_ssh` | Netmiko |
| Nec | `nec_ix_ssh` | Netmiko |
| Netapp | `netapp_cdot_ssh` | Netmiko |
| Netgear | `netgear_prosafe_ssh` | Netmiko |
| Netscaler | `netscaler_ssh` | Netmiko |
| Nokia | `nokia_srl_ssh` | Netmiko |
| Nokia | `nokia_sros_ssh` | Netmiko |
| Oneaccess | `oneaccess_oneos_ssh` | Netmiko |
| Ovs | `ovs_linux_ssh` | Netmiko |
| Palo Alto | `paloalto_panos_ssh` | Netmiko |
| Pluribus | `pluribus_ssh` | Netmiko |
| Quanta | `quanta_mesh_ssh` | Netmiko |
| Rad | `rad_etx_ssh` | Netmiko |
| Raisecom | `raisecom_roap_ssh` | Netmiko |
| Ruckus | `ruckus_fastiron_ssh` | Netmiko |
| Ruijie (锐捷) | `ruijie_os_ssh` | Netmiko |
| Silverpeak | `silverpeak_vxoa_ssh` | Netmiko |
| Sixwind | `sixwind_os_ssh` | Netmiko |
| Sophos | `sophos_sfos_ssh` | Netmiko |
| Supermicro | `supermicro_smis_ssh` | Netmiko |
| Telcosystems | `telcosystems_binos_ssh` | Netmiko |
| Teldat | `teldat_cit_ssh` | Netmiko |
| Tplink | `tplink_jetstream_ssh` | Netmiko |
| Ubiquiti | `ubiquiti_edge_ssh` | Netmiko |
| Ubiquiti | `ubiquiti_edgerouter_ssh` | Netmiko |
| Ubiquiti | `ubiquiti_edgeswitch_ssh` | Netmiko |
| Ubiquiti | `ubiquiti_unifiswitch_ssh` | Netmiko |
| Vertiv | `vertiv_mph_ssh` | Netmiko |
| Vyatta | `vyatta_vyos_ssh` | Netmiko |
| Vyos | `vyos_ssh` | Netmiko |
| Watchguard | `watchguard_fireware_ssh` | Netmiko |
| Yamaha | `yamaha_ssh` | Netmiko |
| ZTE (中兴) | `zte_zxros_ssh` | Netmiko |
| Zyxel | `zyxel_os_ssh` | Netmiko |

## Telnet Supported Devices

| Platform | Device Type | Source |
|----------|-------------|--------|
| Adtran | `adtran_os_telnet` | Netmiko |
| Apresia | `apresia_aeos_telnet` | Netmiko |
| Arista | `arista_eos_telnet` | Netmiko |
| Aruba | `aruba_procurve_telnet` | Netmiko |
| Audiocode | `audiocode_66_telnet` | Netmiko |
| Audiocode | `audiocode_72_telnet` | Netmiko |
| Audiocode | `audiocode_shell_telnet` | Netmiko |
| Bintec | `bintec_boss_telnet` | Netmiko |
| Brocade | `brocade_fastiron_telnet` | Netmiko |
| Brocade | `brocade_netiron_telnet` | Netmiko |
| Calix | `calix_b6_telnet` | Netmiko |
| Centec | `centec_os_telnet` | Netmiko |
| Ciena | `ciena_saos_telnet` | Netmiko |
| Cisco | `cisco_ios_telnet` | Netmiko |
| Cisco | `cisco_nxos_telnet` | Netmiko |
| Cisco | `cisco_s200_telnet` | Netmiko |
| Cisco | `cisco_s300_telnet` | Netmiko |
| Cisco | `cisco_xr_telnet` | Netmiko |
| Dell | `dell_dnos6_telnet` | Netmiko |
| Dell | `dell_powerconnect_telnet` | Netmiko |
| Dlink | `dlink_ds_telnet` | Netmiko |
| Extreme | `extreme_exos_telnet` | Netmiko |
| Extreme | `extreme_netiron_telnet` | Netmiko |
| Extreme | `extreme_telnet` | Netmiko |
| Fiberstore | `fiberstore_fsosv2_telnet` | Netmiko |
| Generic | `generic_telnet` | Netmiko |
| Generic | `generic_termserver_telnet` | Netmiko |
| Genexis | `genexis_solt33_telnet` | Netmiko |
| HP | `hp_comware_telnet` | Netmiko |
| HP | `hp_procurve_telnet` | Netmiko |
| Huawei | `huawei_olt_telnet` | Netmiko |
| Huawei | `huawei_telnet` | Netmiko |
| Huawei | `gns3_huawei_telnet_ce` | Custom ✨ (GNS3) |
| Infinera | `infinera_packet_telnet` | Netmiko |
| Ipinfusion | `ipinfusion_ocnos_telnet` | Netmiko |
| Juniper | `juniper_junos_telnet` | Netmiko |
| Maipu (迈普) | `maipu_telnet` | Netmiko |
| Nec | `nec_ix_telnet` | Netmiko |
| Nokia | `nokia_sros_telnet` | Netmiko |
| Oneaccess | `oneaccess_oneos_telnet` | Netmiko |
| Optilink | `optilink_eolt11444_telnet` | Netmiko |
| Optilink | `optilink_eolt9702_telnet` | Netmiko |
| Palo Alto | `paloalto_panos_telnet` | Netmiko |
| Rad | `rad_etx_telnet` | Netmiko |
| Raisecom | `raisecom_telnet` | Netmiko |
| Ruckus | `ruckus_fastiron_telnet` | Netmiko |
| Ruijie (锐捷) | `ruijie_os_telnet` | Netmiko |
| Ruijie (锐捷) | `gns3_ruijie_telnet` | Custom ✨ (GNS3 Enhanced) |
| Supermicro | `supermicro_smis_telnet` | Netmiko |
| VPCS | `gns3_vpcs_telnet` | Custom ✨ (GNS3 VPCS Simulator) |
| Telcosystems | `telcosystems_binos_telnet` | Netmiko |
| Teldat | `teldat_cit_telnet` | Netmiko |
| Tplink | `tplink_jetstream_telnet` | Netmiko |
| Yamaha | `yamaha_telnet` | Netmiko |
| ZTE (中兴) | `zte_zxros_telnet` | Netmiko |

---

*This document was generated automatically by the Netmiko device list script.*