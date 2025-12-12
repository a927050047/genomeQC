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
  - Uses quartet.py TeloExplorer subcommand with proper parameters:
    - `-c` for organism type (plant/animal/fungi/protist)
    - `-m` for minimum telomere length
    - `-p` for output prefix
  - Falls back to seqkit for basic statistics
  - Lines 231-270
  
- **BUSCO** (`run_busco`):
  - Supports multiple databases
  - Handles both local paths and remote databases
  - Proper offline mode for local databases
  - Lines 299-369
  
- **Merqury** (`run_merqury`):
  - Accepts optional sequencing reads via `--reads` parameter
  - Skips with informative message if no reads provided
  - When reads provided:
    - Uses meryl to count k-mers (k=21) from reads
    - Runs merqury.sh to calculate QV and completeness
    - Supports both cluster and direct execution modes
  - Lines 676-787
  
- **Coverage Analysis** (`run_coverage_analysis`):
  - NEW: Added coverage analysis using minimap2 and mosdepth
  - Accepts optional sequencing reads via `--reads` parameter
  - Skips if no reads provided
  - When reads provided:
    - Aligns reads to assembly using minimap2 (map-ont preset)
    - Converts SAM to sorted BAM using samtools
    - Calculates coverage depth and distribution using mosdepth
    - Supports both cluster and direct execution modes
  - Lines 789-995
  
- **LTR Analysis** (`run_ltr_analysis`):
  - Complete LTR analysis pipeline:
    - gt suffixerator with all required indices (-tis, -suf, -lcp, -des, -ssp, -sds, -dna)
    - gt ltrharvest with specific parameters (minlenltr, maxlenltr, mintsd, maxtsd, motif, etc.)
    - LTR_FINDER_parallel with harvest output format
    - Combines harvest and finder results into rawLTR.scn
    - LTR_retriever for filtering and annotation
    - LAI calculation (if LAI software available)
  - Lines 420-580
  
- **QUAST** (`run_quast`):
  - Calculates N50 and comprehensive assembly statistics
  - Uses --large flag for large genome assemblies
  - Optionally uses reference genome
  - Lines 582-635
  
- **Synteny** (`run_synteny_analysis`):
  - Only runs if reference genome provided
  - Issues warning if GenomeSyn unavailable
  - Lines 502-546

#### 3. Input Parameters

**Requirement**: Accept genome FASTA, threads, BUSCO databases (multiple, local paths supported), output path, optional reference, optional sequencing reads

**Implementation**:
- Command-line argument parser with all required parameters
- Validation of file existence
- Support for multiple BUSCO databases
- Support for multiple sequencing reads files
- Additional parameters:
  - `-c/--organism-type`: Organism type for quartet (plant/animal/fungi/protist)
  - `-m/--min-telomere-length`: Minimum telomere length for quartet
  - `--reads`: Sequencing reads (FASTQ/FASTA) for Merqury and coverage analysis (optional, multiple files)
- Lines 1519-1600

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
  ├── coverage/
  ├── ltr_analysis/
  ├── quast/
  └── synteny/
  ```
- Comprehensive JSON and text summaries including coverage analysis results
- Lines 1382-1475

#### 5. Cluster Support (PBS/Torque)

**Requirement**: Add cluster support, mainly Torque/PBS support, where each software or software group runs as a separate job with proper PBS directives and logging.

**Implementation**:
- `PBSJobManager` class handles PBS script generation and job submission
- PBS script features:
  - Standard PBS directives (#PBS -N, -q, -l nodes:ppn, -j oe, -l walltime)
  - Source ~/.bashrc for environment setup
  - Working directory navigation
  - Automatic log directory creation
  - Timestamped logging with both stdout and stderr capture
  - Format: `exec > >(tee -a $WD/log/$TIME.log $WD/log/$TIME.out) 2> >(tee -a $WD/log/$TIME.err $WD/log/$TIME.out >&2)`
- Separate PBS jobs for each pipeline component:
  - `TELOMERE_GAP`: Telomere and gap analysis
  - `BUSCO_<database>`: One job per BUSCO database
  - `MERQURY`: Merqury QV calculation (if reads provided)
  - `COVERAGE`: Coverage analysis with minimap2 and mosdepth (if reads provided)
  - `LTR_ANALYSIS`: Complete LTR pipeline (ltrharvest, LTR_FINDER, LTR_retriever, LAI)
  - `QUAST`: Assembly statistics
  - `SYNTENY`: Synteny analysis (if reference provided)
- Command-line options:
  - `--cluster`: Enable cluster mode
  - `--pbs-queue`: Queue name (default: high)
  - `--pbs-nodes`: Number of nodes (default: 1)
  - `--pbs-ppn`: Processors per node (default: 60)
  - `--pbs-walltime`: Walltime (default: 240:00:00)
  - `--dry-run`: Generate scripts without submitting
- Job dependency tracking for future enhancements
- Lines 32-145 (PBSJobManager), cluster mode logic in each analysis method

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
  - 使用quartet.py TeloExplorer子命令及适当参数:
    - `-c` 指定生物类型 (plant/animal/fungi/protist)
    - `-m` 指定最小端粒长度
    - `-p` 指定输出前缀
  - 回退到seqkit进行基本统计
  - 第231-270行
  
- **BUSCO** (`run_busco`):
  - 支持多个数据库
  - 处理本地路径和远程数据库
  - 本地数据库正确使用离线模式
  - 第299-369行
  
- **Merqury** (`run_merqury`):
  - 通过`--reads`参数接受可选的测序数据
  - 如果未提供reads则跳过并显示提示信息
  - 当提供reads时:
    - 使用meryl从reads计数k-mer (k=21)
    - 运行merqury.sh计算QV和完整性
    - 支持集群和直接执行模式
  - 第676-787行
  
- **覆盖度分析** (`run_coverage_analysis`):
  - 新增：使用minimap2和mosdepth进行覆盖度分析
  - 通过`--reads`参数接受可选的测序数据
  - 如果未提供reads则跳过
  - 当提供reads时:
    - 使用minimap2将reads比对到组装序列 (map-ont预设)
    - 使用samtools将SAM转换为排序的BAM
    - 使用mosdepth计算覆盖深度和分布
    - 支持集群和直接执行模式
  - 第789-995行
  
- **LTR分析** (`run_ltr_analysis`):
  - 完整的LTR分析流程:
    - gt suffixerator 创建所有必需索引 (-tis, -suf, -lcp, -des, -ssp, -sds, -dna)
    - gt ltrharvest 使用特定参数 (minlenltr, maxlenltr, mintsd, maxtsd, motif等)
    - LTR_FINDER_parallel 生成harvest格式输出
    - 合并harvest和finder结果为rawLTR.scn
    - LTR_retriever 进行过滤和注释
    - LAI计算（如果LAI软件可用）
  - 第420-580行
  
- **QUAST** (`run_quast`):
  - 计算N50和全面的组装统计
  - 使用--large标志处理大型基因组组装
  - 可选使用参考基因组
  - 第582-635行
  
- **共线性** (`run_synteny_analysis`):
  - 仅在提供参考基因组时运行
  - 如果GenomeSyn不可用则发出警告
  - 第502-546行

#### 3. 输入参数

**需求**: 接受基因组fasta，线程数，busco数据库（可多个，可本地路径），输出路径，可选参考基因组，可选测序数据

**实现**:
- 包含所有必需参数的命令行参数解析器
- 文件存在性验证
- 支持多个BUSCO数据库
- 支持多个测序reads文件
- 附加参数:
  - `-c/--organism-type`: quartet使用的生物类型 (plant/animal/fungi/protist)
  - `-m/--min-telomere-length`: quartet使用的最小端粒长度
  - `--reads`: 测序数据 (FASTQ/FASTA) 用于Merqury和覆盖度分析（可选，可多个文件）
- 第1519-1600行

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
  ├── coverage/
  ├── ltr_analysis/
  ├── quast/
  └── synteny/
  ```
- 全面的JSON和文本摘要，包括覆盖度分析结果
- 第1382-1475行

#### 5. 集群支持 (PBS/Torque)

**需求**: 添加集群支持，主要是Torque/PBS支持，每个软件或软件组单独运行一个任务，包含适当的PBS指令和日志记录。

**实现**:
- `PBSJobManager` 类处理PBS脚本生成和作业提交
- PBS脚本特性:
  - 标准PBS指令 (#PBS -N, -q, -l nodes:ppn, -j oe, -l walltime)
  - Source ~/.bashrc 用于环境设置
  - 工作目录导航
  - 自动创建日志目录
  - 带时间戳的日志记录，同时捕获stdout和stderr
  - 格式: `exec > >(tee -a $WD/log/$TIME.log $WD/log/$TIME.out) 2> >(tee -a $WD/log/$TIME.err $WD/log/$TIME.out >&2)`
- 每个流程组件单独的PBS作业:
  - `TELOMERE_GAP`: 端粒和gap分析
  - `BUSCO_<database>`: 每个BUSCO数据库一个作业
  - `MERQURY`: Merqury QV计算（如果提供reads）
  - `COVERAGE`: 使用minimap2和mosdepth的覆盖度分析（如果提供reads）
  - `LTR_ANALYSIS`: 完整的LTR流程 (ltrharvest, LTR_FINDER, LTR_retriever, LAI)
  - `QUAST`: 组装统计
  - `SYNTENY`: 共线性分析（如果提供参考基因组）
- 命令行选项:
  - `--cluster`: 启用集群模式
  - `--pbs-queue`: 队列名称（默认：high）
  - `--pbs-nodes`: 节点数（默认：1）
  - `--pbs-ppn`: 每节点处理器数（默认：60）
  - `--pbs-walltime`: 运行时间限制（默认：240:00:00）
  - `--dry-run`: 生成脚本但不提交
- 作业依赖跟踪，用于未来增强
- 第32-145行 (PBSJobManager)，每个分析方法中的集群模式逻辑

### 使用示例

```bash
# 基本使用
python genomeQC.py -g genome.fasta -o results -t 16 -b eukaryota_odb10

# 使用多个BUSCO数据库
python genomeQC.py -g genome.fasta -o results -t 32 -b eukaryota_odb10 metazoa_odb10

# 使用本地BUSCO数据库
python genomeQC.py -g genome.fasta -o results -t 16 -b /path/to/eukaryota_odb10

# 植物基因组分析（类似问题描述中的示例）
python genomeQC.py -g genome.fasta -o results -t 20 -b embryophyta_odb10 -c plant -m 50

# 包含参考基因组进行共线性分析
python genomeQC.py -g genome.fasta -o results -t 32 -b eukaryota_odb10 -r reference.fasta -c plant -m 50

# 使用测序数据进行Merqury和覆盖度分析
python genomeQC.py -g genome.fasta -o results -t 16 -b eukaryota_odb10 --reads reads.fastq.gz

# 使用多个测序文件
python genomeQC.py -g genome.fasta -o results -t 16 -b eukaryota_odb10 --reads reads1.fastq.gz reads2.fastq.gz

# 集群模式 - 生成并提交PBS作业
python genomeQC.py -g genome.fasta -o results -t 60 -b eukaryota_odb10 --cluster --pbs-queue high --pbs-ppn 60

# 集群模式 - 仅生成脚本不提交（dry run）
python genomeQC.py -g genome.fasta -o results -t 60 -b eukaryota_odb10 --cluster --dry-run

# 集群模式 - 使用测序数据
python genomeQC.py -g genome.fasta -o results -t 60 -b eukaryota_odb10 --reads reads.fastq.gz --cluster
```

### 注意事项

1. **quartet**: 必须单独安装，如不可用则使用seqkit（无可视化）
   - 使用TeloExplorer子命令
   - 支持organism type配置（-c参数）
   - 支持最小端粒长度配置（-m参数）
2. **GenomeSyn**: 必须单独安装，如不可用且提供了参考基因组，将输出警告并跳过
3. **Merqury**: 需要原始测序reads生成k-mer数据库。通过`--reads`选项提供reads。
   - 使用meryl从测序reads计数k-mer (k=21)
   - 计算组装质量值(QV)和完整性
4. **覆盖度分析**: 需要原始测序reads进行比对和覆盖度计算。通过`--reads`选项提供reads。
   - 使用minimap2进行比对（使用map-ont预设用于Nanopore reads；根据需要调整）
   - 使用samtools处理BAM文件
   - 使用mosdepth进行覆盖深度和分布分析
5. **LAI**: 需要额外的LAI软件安装才能完成计算
6. **LTR_FINDER_parallel**: 可选工具，如不可用则仅使用ltrharvest结果
7. **QUAST**: 使用--large标志适用于大型基因组
