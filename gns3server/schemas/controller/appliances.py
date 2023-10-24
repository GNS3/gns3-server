#
# Copyright (C) 2021 GNS3 Technologies Inc.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

# Generated from JSON schema using https://github.com/koxudaxi/datamodel-code-generator

from enum import Enum
from typing import List, Optional, Union
from uuid import UUID
from pydantic import AnyUrl, BaseModel, EmailStr, Field, confloat, conint, constr


class Category(str, Enum):

    router = 'router'
    multilayer_switch = 'multilayer_switch'
    switch = 'switch'
    firewall = 'firewall'
    guest = 'guest'


class RegistryVersion(int, Enum):

    version1 = 1
    version2 = 2
    version3 = 3
    version4 = 4
    version5 = 5
    version6 = 6


class Status(str, Enum):

    stable = 'stable'
    experimental = 'experimental'
    broken = 'broken'


class Availability(str, Enum):

    free = 'free'
    with_registration = 'with-registration'
    free_to_try = 'free-to-try'
    service_contract = 'service-contract'


class ConsoleType(str, Enum):

    telnet = 'telnet'
    vnc = 'vnc'
    http = 'http'
    https = 'https'
    none = 'none'


class Docker(BaseModel):

    adapters: int = Field(..., title='Number of ethernet adapters')
    image: str = Field(..., title='Docker image in the Docker Hub')
    start_command: Optional[str] = Field(
        None,
        title='Command executed when the container start. Empty will use the default',
    )
    environment: Optional[str] = Field(None, title='One KEY=VAR environment by line')
    console_type: Optional[ConsoleType] = Field(
        None, title='Type of console connection for the administration of the appliance'
    )
    console_http_port: Optional[int] = Field(
        None, description='Internal port in the container of the HTTP server'
    )
    console_http_path: Optional[str] = Field(
        None, description='Path of the web interface'
    )
    extra_hosts: Optional[str] = Field(
        None, description='Hosts which will be written to /etc/hosts into container'
    )
    extra_volumes: Optional[List[str]] = Field(
        None,
        description='Additional directories to make persistent that are not included in the images VOLUME directive',
    )


class Iou(BaseModel):

    ethernet_adapters: int = Field(..., title='Number of ethernet adapters')
    serial_adapters: int = Field(..., title='Number of serial adapters')
    nvram: int = Field(..., title='Host NVRAM')
    ram: int = Field(..., title='Host RAM')
    startup_config: str = Field(..., title='Config loaded at startup')


class Chassis(str, Enum):

    chassis_1720 = '1720'
    chassis_1721 = '1721'
    chassis_1750 = '1750'
    chassis_1751 = '1751'
    chassis_1760 = '1760'
    chassis_2610 = '2610'
    chassis_2620 = '2620'
    chassis_2610XM = '2610XM'
    chassis_2620XM = '2620XM'
    chassis_2650XM = '2650XM'
    chassis_2621 = '2621'
    chassis_2611XM = '2611XM'
    chassis_2621XM = '2621XM'
    chassis_2651XM = '2651XM'
    chassis_3620 = '3620'
    chassis_3640 = '3640'
    chassis_3660 = '3660'


class Platform(str, Enum):

    c1700 = 'c1700'
    c2600 = 'c2600'
    c2691 = 'c2691'
    c3725 = 'c3725'
    c3745 = 'c3745'
    c3600 = 'c3600'
    c7200 = 'c7200'


class Midplane(str, Enum):

    std = 'std'
    vxr = 'vxr'


class Npe(str, Enum):

    npe_100 = 'npe-100'
    npe_150 = 'npe-150'
    npe_175 = 'npe-175'
    npe_200 = 'npe-200'
    npe_225 = 'npe-225'
    npe_300 = 'npe-300'
    npe_400 = 'npe-400'
    npe_g2 = 'npe-g2'


class AdapterType(str, Enum):

    e1000 = 'e1000'
    e1000_82544gc = 'e1000-82544gc'
    e1000_82545em = 'e1000-82545em'
    e1000e = 'e1000e'
    i82550 = 'i82550'
    i82551 = 'i82551'
    i82557a = 'i82557a'
    i82557b = 'i82557b'
    i82557c = 'i82557c'
    i82558a = 'i82558a'
    i82558b = 'i82558b'
    i82559a = 'i82559a'
    i82559b = 'i82559b'
    i82559c = 'i82559c'
    i82559er = 'i82559er'
    i82562 = 'i82562'
    i82801 = 'i82801'
    igb = 'igb'
    ne2k_pci = 'ne2k_pci'
    pcnet = 'pcnet'
    rocker = 'rocker'
    rtl8139 = 'rtl8139'
    virtio = 'virtio'
    virtio_net_pci = 'virtio-net-pci'
    vmxnet3 = 'vmxnet3'


class DiskInterface(str, Enum):

    ide = 'ide'
    sata = 'sata'
    nvme = 'nvme'
    scsi = 'scsi'
    sd = 'sd'
    mtd = 'mtd'
    floppy = 'floppy'
    pflash = 'pflash'
    virtio = 'virtio'
    none = 'none'


class Arch(str, Enum):

    aarch64 = 'aarch64'
    alpha = 'alpha'
    arm = 'arm'
    cris = 'cris'
    i386 = 'i386'
    lm32 = 'lm32'
    m68k = 'm68k'
    microblaze = 'microblaze'
    microblazeel = 'microblazeel'
    mips = 'mips'
    mips64 = 'mips64'
    mips64el = 'mips64el'
    mipsel = 'mipsel'
    moxie = 'moxie'
    or32 = 'or32'
    ppc = 'ppc'
    ppc64 = 'ppc64'
    ppcemb = 'ppcemb'
    s390x = 's390x'
    sh4 = 'sh4'
    sh4eb = 'sh4eb'
    sparc = 'sparc'
    sparc64 = 'sparc64'
    tricore = 'tricore'
    unicore32 = 'unicore32'
    x86_64 = 'x86_64'
    xtensa = 'xtensa'
    xtensaeb = 'xtensaeb'


class ConsoleType1(str, Enum):

    telnet = 'telnet'
    vnc = 'vnc'
    spice = 'spice'
    spice_agent = 'spice+agent'
    none = 'none'


class BootPriority(str, Enum):

    c = 'c'
    d = 'd'
    n = 'n'
    cn = 'cn'
    cd = 'cd'
    dn = 'dn'
    dc = 'dc'
    nc = 'nc'
    nd = 'nd'


class Kvm(str, Enum):

    require = 'require'
    allow = 'allow'
    disable = 'disable'


class ProcessPriority(str, Enum):

    realtime = 'realtime'
    very_high = 'very high'
    high = 'high'
    normal = 'normal'
    low = 'low'
    very_low = 'very low'
    null = 'null'


class Qemu(BaseModel):

    adapter_type: AdapterType = Field(..., title='Type of network adapter')
    adapters: int = Field(..., title='Number of adapters')
    ram: int = Field(..., title='Ram allocated to the appliance (MB)')
    cpus: Optional[int] = Field(None, title='Number of Virtual CPU')
    hda_disk_interface: Optional[DiskInterface] = Field(
        None, title='Disk interface for the installed hda_disk_image'
    )
    hdb_disk_interface: Optional[DiskInterface] = Field(
        None, title='Disk interface for the installed hdb_disk_image'
    )
    hdc_disk_interface: Optional[DiskInterface] = Field(
        None, title='Disk interface for the installed hdc_disk_image'
    )
    hdd_disk_interface: Optional[DiskInterface] = Field(
        None, title='Disk interface for the installed hdd_disk_image'
    )
    arch: Arch = Field(..., title='Architecture emulated')
    console_type: ConsoleType1 = Field(
        ..., title='Type of console connection for the administration of the appliance'
    )
    boot_priority: Optional[BootPriority] = Field(
        None,
        title='Disk boot priority. Refer to -boot option in qemu manual for more details.',
    )
    kernel_command_line: Optional[str] = Field(
        None, title='Command line parameters send to the kernel'
    )
    kvm: Kvm = Field(..., title='KVM requirements')
    options: Optional[str] = Field(
        None, title='Optional additional qemu command line options'
    )
    cpu_throttling: Optional[confloat(ge=0.0, le=100.0)] = Field(
        None, title='Throttle the CPU'
    )
    process_priority: Optional[ProcessPriority] = Field(
        None, title='Process priority for QEMU'
    )


class Compression(str, Enum):

    bzip2 = 'bzip2'
    gzip = 'gzip'
    lzma = 'lzma'
    xz = 'xz'
    rar = 'rar'
    zip = 'zip'
    field_7z = '7z'


class ApplianceImage(BaseModel):

    filename: str = Field(..., title='Filename')
    version: str = Field(..., title='Version of the file')
    md5sum: str = Field(..., title='md5sum of the file', pattern='^[a-f0-9]{32}$')
    filesize: int = Field(..., title='File size in bytes')
    download_url: Optional[Union[AnyUrl, constr(max_length=0)]] = Field(
        None, title='Download url where you can download the appliance from a browser'
    )
    direct_download_url: Optional[Union[AnyUrl, constr(max_length=0)]] = Field(
        None,
        title='Optional. Non authenticated url to the image file where you can download the image.',
    )
    compression: Optional[Compression] = Field(
        None, title='Optional, compression type of direct download url image.'
    )


class ApplianceVersionImages(BaseModel):

    kernel_image: Optional[str] = Field(None, title='Kernel image')
    initrd: Optional[str] = Field(None, title='Initrd disk image')
    image: Optional[str] = Field(None, title='OS image')
    bios_image: Optional[str] = Field(None, title='Bios image')
    hda_disk_image: Optional[str] = Field(None, title='Hda disk image')
    hdb_disk_image: Optional[str] = Field(None, title='Hdc disk image')
    hdc_disk_image: Optional[str] = Field(None, title='Hdd disk image')
    hdd_disk_image: Optional[str] = Field(None, title='Hdd diskimage')
    cdrom_image: Optional[str] = Field(None, title='cdrom image')


class ApplianceVersion(BaseModel):

    name: str = Field(..., title='Name of the version')
    idlepc: Optional[str] = Field(None, pattern='^0x[0-9a-f]{8}')
    images: Optional[ApplianceVersionImages] = Field(None, title='Images used for this version')


class DynamipsSlot(str, Enum):

    C7200_IO_2FE = 'C7200-IO-2FE'
    C7200_IO_FE = 'C7200-IO-FE'
    C7200_IO_GE_E = 'C7200-IO-GE-E'
    NM_16ESW = 'NM-16ESW'
    NM_1E = 'NM-1E'
    NM_1FE_TX = 'NM-1FE-TX'
    NM_4E = 'NM-4E'
    NM_4T = 'NM-4T'
    PA_2FE_TX = 'PA-2FE-TX'
    PA_4E = 'PA-4E'
    PA_4T_ = 'PA-4T+'
    PA_8E = 'PA-8E'
    PA_8T = 'PA-8T'
    PA_A1 = 'PA-A1'
    PA_FE_TX = 'PA-FE-TX'
    PA_GE = 'PA-GE'
    PA_POS_OC3 = 'PA-POS-OC3'
    C2600_MB_2FE = 'C2600-MB-2FE'
    C2600_MB_1E = 'C2600-MB-1E'
    C1700_MB_1FE = 'C1700-MB-1FE'
    C2600_MB_2E = 'C2600-MB-2E'
    C2600_MB_1FE = 'C2600-MB-1FE'
    C1700_MB_WIC1 = 'C1700-MB-WIC1'
    GT96100_FE = 'GT96100-FE'
    Leopard_2FE = 'Leopard-2FE'
    _ = ''


class DynamipsWic(str, Enum):

    WIC_1ENET = 'WIC-1ENET'
    WIC_1T = 'WIC-1T'
    WIC_2T = 'WIC-2T'


class Dynamips(BaseModel):

    chassis: Optional[Chassis] = Field(None, title='Chassis type')
    platform: Platform = Field(..., title='Platform type')
    ram: conint(ge=1) = Field(..., title='Amount of ram')
    nvram: conint(ge=1) = Field(..., title='Amount of nvram')
    startup_config: Optional[str] = Field(None, title='Config loaded at startup')
    wic0: Optional[DynamipsWic] = None
    wic1: Optional[DynamipsWic] = None
    wic2: Optional[DynamipsWic] = None
    slot0: Optional[DynamipsSlot] = None
    slot1: Optional[DynamipsSlot] = None
    slot2: Optional[DynamipsSlot] = None
    slot3: Optional[DynamipsSlot] = None
    slot4: Optional[DynamipsSlot] = None
    slot5: Optional[DynamipsSlot] = None
    slot6: Optional[DynamipsSlot] = None
    midplane: Optional[Midplane] = None
    npe: Optional[Npe] = None


class Appliance(BaseModel):

    appliance_id: UUID = Field(..., title='Appliance ID')
    name: str = Field(..., title='Appliance name')
    builtin: Optional[bool] = Field(None, title='Whether the appliance is builtin or not')
    category: Category = Field(..., title='Category of the appliance')
    description: str = Field(
        ..., title='Description of the appliance. Could be a marketing description'
    )
    vendor_name: str = Field(..., title='Name of the vendor')
    vendor_url: Optional[Union[AnyUrl, constr(max_length=0)]] = Field(None, title='Website of the vendor')
    documentation_url: Optional[Union[AnyUrl, constr(max_length=0)]] = Field(
        None,
        title='An optional documentation for using the appliance on vendor website',
    )
    product_name: str = Field(..., title='Product name')
    product_url: Optional[Union[AnyUrl, constr(max_length=0)]] = Field(
        None, title='An optional product url on vendor website'
    )
    registry_version: RegistryVersion = Field(
        ..., title='Version of the registry compatible with this appliance'
    )
    status: Status = Field(..., title='Document if the appliance is working or not')
    availability: Optional[Availability] = Field(
        None,
        title='About image availability: can be downloaded directly; download requires a free registration; paid but a trial version (time or feature limited) is available; not available publicly',
    )
    maintainer: str = Field(..., title='Maintainer name')
    maintainer_email: Optional[Union[EmailStr, constr(max_length=0)]] = Field(None, title='Maintainer email')
    usage: Optional[str] = Field(None, title='How to use the appliance')
    symbol: Optional[str] = Field(None, title='An optional symbol for the appliance')
    first_port_name: Optional[str] = Field(
        None, title='Optional name of the first networking port example: eth0'
    )
    port_name_format: Optional[str] = Field(
        None, title='Optional formating of the networking port example: eth{0}'
    )
    port_segment_size: Optional[int] = Field(
        None,
        title='Optional port segment size. A port segment is a block of port. For example Ethernet0/0 Ethernet0/1 is the module 0 with a port segment size of 2',
    )
    linked_clone: Optional[bool] = Field(
        None, title="False if you don't want to use a single image for all nodes"
    )
    docker: Optional[Docker] = Field(None, title='Docker specific options')
    iou: Optional[Iou] = Field(None, title='IOU specific options')
    dynamips: Optional[Dynamips] = Field(None, title='Dynamips specific options')
    qemu: Optional[Qemu] = Field(None, title='Qemu specific options')
    images: Optional[List[ApplianceImage]] = Field(None, title='Images for this appliance')
    versions: Optional[List[ApplianceVersion]] = Field(None, title='Versions of the appliance')
