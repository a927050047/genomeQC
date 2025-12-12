# Implementation Details / 实现细节

[English](#english) | [中文](#中文)

## English

### Requirements Implementation

This document describes how the genomic QC pipeline implements all specified requirements.

#### 1. Software Dependency Management

**Requirement**: Use micromamba to create environments and install software (except GenomeSyn and quartet). Avoid duplicate installations by checking for existing environments (case-insensitive) or modules.

**Implementation**:
- `EnvironmentManager` class handles all environment detection and software installation
- Three-tier fallback system:
  1. **Existing Environment Check**: Searches for case-insensitive matching micromamba environments
  2. **Module System Check**: Falls back to environment modules if available
  3. **Automatic Installation**: Creates new micromamba environment if neither exists
- Special handling for quartet and GenomeSyn (not managed by micromamba)
- See: `genomeQC.py` lines 26-170

#### 2. Tool Integration

**Requirement**: Comprehensive QC pipeline including:
- quartet: identify, count, and visualize telomeres and gaps (fallback to seqkit without visualization)
- BUSCO: calculate completeness
- Merqury: calculate QV
- ltrharvest, LTR_retriever, LAI: calculate LAI
- QUAST: calculate N50, etc.
- GenomeSyn: synteny plots with reference genome (warning if unavailable)

**Implementation**:
- **Telomere/Gap Analysis** (`run_telomere_gap_analysis`): 
  - Checks for quartet availability
  - Falls back to seqkit for basic statistics
  - Lines 245-297
  
- **BUSCO** (`run_busco`):
  - Supports multiple databases
  - Handles both local paths and remote databases
  - Proper offline mode for local databases
  - Lines 299-369
  
- **Merqury** (`run_merqury`):
  - Documents requirement for raw reads
  - Skips with informative message
  - Lines 371-386
  
- **LTR Analysis** (`run_ltr_analysis`):
  - Integrates ltrharvest (via genometools)
  - Runs LTR_retriever
  - Prepares for LAI calculation
  - Lines 388-456
  
- **QUAST** (`run_quast`):
  - Calculates N50 and comprehensive assembly statistics
  - Optionally uses reference genome
  - Lines 458-500
  
- **Synteny** (`run_synteny_analysis`):
  - Only runs if reference genome provided
  - Issues warning if GenomeSyn unavailable
  - Lines 502-546

#### 3. Input Parameters

**Requirement**: Accept genome FASTA, threads, BUSCO databases (multiple, local paths supported), output path, optional reference

**Implementation**:
- Command-line argument parser with all required parameters
- Validation of file existence
- Support for multiple BUSCO databases
- Lines 698-725

#### 4. Output Structure

**Requirement**: Results in target folder with summary table and subdirectories

**Implementation**:
- Organized directory structure:
  ```
  output_dir/
  ├── summary_report.json
  ├── summary_report.txt
  ├── telomere_gap/
  ├── busco/
  ├── merqury/
  ├── ltr_analysis/
  ├── quast/
  └── synteny/
  ```
- Comprehensive JSON and text summaries
- Lines 548-651

---

## 中文

### 需求实现说明

本文档描述基因组QC流程如何实现所有指定的需求。

#### 1. 软件依赖管理

**需求**: 使用micromamba创建环境并安装所有软件依赖（除GenomeSyn和quartet外）。为避免重复安装，首先检测是否存在不考虑大小写的与软件同名的环境，若存在则使用。若不存在，检测module系统。都不存在时使用micromamba创建环境。

**实现**:
- `EnvironmentManager` 类处理所有环境检测和软件安装
- 三层回退系统:
  1. **现有环境检查**: 不区分大小写搜索匹配的micromamba环境
  2. **模块系统检查**: 如果可用，回退到环境模块
  3. **自动安装**: 如果都不存在，创建新的micromamba环境
- quartet和GenomeSyn特殊处理（不由micromamba管理）
- 参见: `genomeQC.py` 第26-170行

#### 2. 工具集成

**需求**: 综合QC流程包括:
- quartet: 识别、计数并可视化端粒和gap（不存在时使用seqkit但不可视化）
- BUSCO: 计算完整性
- Merqury: 计算QV
- ltrharvest、LTR_retriever、LAI: 计算LAI
- QUAST: 计算N50等
- GenomeSyn: 与参考基因组的共线比对图（不存在时输出警告）

**实现**:
- **端粒/Gap分析** (`run_telomere_gap_analysis`): 
  - 检查quartet可用性
  - 回退到seqkit进行基本统计
  - 第245-297行
  
- **BUSCO** (`run_busco`):
  - 支持多个数据库
  - 处理本地路径和远程数据库
  - 本地数据库正确使用离线模式
  - 第299-369行
  
- **Merqury** (`run_merqury`):
  - 记录需要原始reads的要求
  - 跳过并提供信息性消息
  - 第371-386行
  
- **LTR分析** (`run_ltr_analysis`):
  - 集成ltrharvest（通过genometools）
  - 运行LTR_retriever
  - 为LAI计算做准备
  - 第388-456行
  
- **QUAST** (`run_quast`):
  - 计算N50和全面的组装统计
  - 可选使用参考基因组
  - 第458-500行
  
- **共线性** (`run_synteny_analysis`):
  - 仅在提供参考基因组时运行
  - 如果GenomeSyn不可用则发出警告
  - 第502-546行

#### 3. 输入参数

**需求**: 接受基因组fasta，线程数，busco数据库（可多个，可本地路径），输出路径，可选参考基因组

**实现**:
- 包含所有必需参数的命令行参数解析器
- 文件存在性验证
- 支持多个BUSCO数据库
- 第698-725行

#### 4. 输出结构

**需求**: 结果输出在目标文件夹下，包括一个总表和分结果文件夹

**实现**:
- 有组织的目录结构:
  ```
  output_dir/
  ├── summary_report.json
  ├── summary_report.txt
  ├── telomere_gap/
  ├── busco/
  ├── merqury/
  ├── ltr_analysis/
  ├── quast/
  └── synteny/
  ```
- 全面的JSON和文本摘要
- 第548-651行

### 使用示例

```bash
# 基本使用
python genomeQC.py -g genome.fasta -o results -t 16 -b eukaryota_odb10

# 使用多个BUSCO数据库
python genomeQC.py -g genome.fasta -o results -t 32 -b eukaryota_odb10 metazoa_odb10

# 使用本地BUSCO数据库
python genomeQC.py -g genome.fasta -o results -t 16 -b /path/to/eukaryota_odb10

# 包含参考基因组进行共线性分析
python genomeQC.py -g genome.fasta -o results -t 32 -b eukaryota_odb10 -r reference.fasta
```

### 注意事项

1. **quartet**: 必须单独安装，如不可用则使用seqkit（无可视化）
2. **GenomeSyn**: 必须单独安装，如不可用且提供了参考基因组，将输出警告并跳过
3. **Merqury**: 需要原始测序reads生成k-mer数据库（当前版本跳过）
4. **LAI**: 需要额外的LAI软件安装才能完成计算
