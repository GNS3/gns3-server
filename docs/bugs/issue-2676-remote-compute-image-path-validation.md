# Issue #2676: 远程计算节点镜像路径验证失败

## 问题描述

当在远程计算节点上创建 IOU 节点时，控制器将其本地绝对镜像路径发送给计算节点，但计算节点拒绝该路径，因为它与计算节点配置的镜像目录不匹配。

## 错误信息

```
'/home/gns3/GNS3/images/IOU/i86bi-linux-l3-adventerprisek9-15.4.1T.bin' is not allowed on this remote server. Please only use a file from '/home/yueguobin/GNS3/images/IOU'
```

## 根本原因

### 架构说明

GNS3 采用控制器-计算节点分离架构：
- **Controller（控制节点）**：管理拓扑，负责节点创建、连接等逻辑
- **Compute（计算节点）**：实际运行虚拟机，执行节点操作

### 问题详细分析

#### 1. 控制器发送绝对路径

在 `gns3server/controller/node.py` 的 `_node_data()` 方法中，控制器准备节点数据时，直接将本地镜像的绝对路径发送给计算节点：

```python
# 控制器端的镜像路径是控制器的本地路径
path = "/home/gns3/GNS3/images/IOU/i86bi-linux-l3-adventerprisek9-15.4.1T.bin"
data["path"] = path  # 发送给计算节点
```

#### 2. 计算节点验证路径

在 `gns3server/compute/base_manager.py` 的 `get_abs_image_path()` 方法中（第448-456行）：

```python
# 如果是绝对路径，检查是否在计算节点的允许目录中
if os.path.isabs(orig_path):
    for directory in valid_directory_prefices:
        if os.path.commonprefix([directory, path]) == directory:
            if os.path.exists(path):
                return path
            raise ImageMissingError(orig_path)
    # 路径前缀不匹配，抛出错误
    raise NodeError(f"'{path}' is not allowed on this remote server...")
```

#### 3. 路径不匹配

- **控制器** 的镜像目录：`/home/gns3/GNS3/images`
- **计算节点** 的镜像目录：`/home/yueguobin/GNS3/images`
- 路径前缀检查 `os.path.commonprefix([directory, path]) == directory` 失败
- 抛出 `NodeError`，节点创建失败

### 为什么不触发镜像上传？

控制器有自动上传缺失镜像的机制（`_upload_missing_image()`），但这个机制只在收到 `ImageMissingError` 时触发。

由于计算节点抛出的是 `NodeError` 而不是 `ImageMissingError`，控制器无法触发自动上传逻辑。

## 影响范围

此问题影响所有使用镜像文件的节点类型：

| 节点类型 | 镜像路径字段 | 状态 |
|---------|------------|------|
| **IOU** | `path` | ❌ 受影响 |
| **QEMU** | `hda_disk_image`, `hdb_disk_image`, `hdc_disk_image`, `hdd_disk_image`<br>`cdrom_image`, `bios_image`, `initrd`, `kernel_image` | ❌ 受影响 |
| **Dynamips (IOS)** | `image` | ❌ 受影响 |
| **VMware** | `vmx_path` | ❌ 受影响 |
| **Docker** | `image` (Docker 镜像名称，非文件路径) | ✅ 不受影响 |

## 解决方案

### 实现方案

修改控制器端的 `_node_data()` 方法，对远程计算节点发送相对路径（仅文件名）而非绝对路径。

**文件**: `gns3server/controller/node.py`

**修改位置**: 第541-546行

```python
# For remote computes, convert absolute image paths to relative paths
# The remote compute will search for the image in its own configured directories
if self._compute.id != "local" and "path" in data and os.path.isabs(data["path"]):
    data["path"] = os.path.basename(data["path"])
```

### 工作原理

#### 1. 控制器发送相对路径

```python
# 原来发送："/home/gns3/GNS3/images/IOU/i86bi-linux-l3-adventerprisek9-15.4.1T.bin"
# 现在发送："i86bi-linux-l3-adventerprisek9-15.4.1T.bin"
if self._compute.id != "local" and "path" in data and os.path.isabs(data["path"]):
    data["path"] = os.path.basename(data["path"])
```

#### 2. 计算节点搜索镜像

计算节点的 `get_abs_image_path()` 方法处理相对路径（第432-446行）：

```python
if not os.path.isabs(orig_path):
    for directory in valid_directory_prefices:
        path = self._recursive_search_file_in_directory(directory, orig_path)
        if path:
            return force_unix_path(path)
    # 未找到，抛出 ImageMissingError
    raise ImageMissingError(orig_path)
```

计算节点在其配置的镜像目录中搜索：
- 默认目录：`~/GNS3/images/IOU`（从配置文件 `gns3_server.conf` 读取）
- 额外目录：`Server.additional_images_paths` 中配置的目录

#### 3. 自动上传机制

如果计算节点未找到镜像，返回 `ImageMissingError`，控制器捕获后自动上传：

```python
except ComputeConflictError as e:
    response = e.response()
    if response.get("exception") == "ImageMissingError":
        res = await self._upload_missing_image(self._node_type, response["image"])
```

### 向后兼容性

- **本地计算节点**（`id == "local"`）：不受影响，继续使用绝对路径
- **远程计算节点**（`id != "local"`）：使用相对路径，由计算节点在其目录中搜索

## 测试场景

### 场景 1：镜像已存在于计算节点

1. 控制器创建节点，发送相对路径 `i86bi-linux-l3-adventerprisek9-15.4.1T.bin`
2. 计算节点在 `~/GNS3/images/IOU/` 中找到镜像
3. 节点创建成功 ✅

### 场景 2：镜像不存在于计算节点

1. 控制器创建节点，发送相对路径 `i86bi-linux-l3-adventerprisek9-15.4.1T.bin`
2. 计算节点未找到镜像，返回 `ImageMissingError`
3. 控制器自动上传镜像到计算节点
4. 重试创建，节点创建成功 ✅

### 场景 3：同名但内容不同的镜像

⚠️ **潜在风险**：如果计算节点已存在同名镜像但内容不同（不同版本），不会触发上传，可能使用错误的镜像。

**建议改进**：未来可以添加 MD5 校验和验证，确保使用正确的镜像版本。

## 当前状态

- ✅ IOU 节点已修复
- ⏳ 其他节点类型（QEMU, Dynamips, VMware）需要类似的修复

## 相关文件

- `gns3server/controller/node.py` - 控制器节点实现
- `gns3server/compute/base_manager.py` - 计算节点基础管理器
- `gns3server/compute/iou/iou_vm.py` - IOU 节点实现
- `gns3server/utils/images.py` - 镜像工具函数

## 参考

- GitHub Issue: #2676
- 修复分支: `fix/iou-remote-path-validation`
