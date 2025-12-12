# Cluster Mode for genomeQC

This document provides comprehensive information about using genomeQC in cluster mode with PBS/Torque job scheduling systems.

## Overview

Cluster mode allows genomeQC to run on HPC (High-Performance Computing) environments by generating PBS job scripts for each pipeline component and submitting them to the job scheduler. This is ideal for:

- Large genome assemblies requiring significant computational resources
- HPC environments with PBS/Torque job schedulers
- Running multiple analyses in parallel on different compute nodes
- Better resource management and job tracking

## Quick Start

### Basic Cluster Mode Usage

```bash
python genomeQC.py \
    --genome genome.fasta \
    --output ./results \
    --threads 60 \
    --busco eukaryota_odb10 \
    --cluster \
    --pbs-queue high \
    --pbs-ppn 60
```

### Dry Run (Preview Scripts Without Submitting)

```bash
python genomeQC.py \
    --genome genome.fasta \
    --output ./results \
    --threads 60 \
    --busco eukaryota_odb10 \
    --cluster \
    --dry-run
```

## Command-Line Options

### Cluster Mode Flags

- `--cluster`: Enable cluster mode (required for PBS job generation)
- `--pbs-queue QUEUE`: PBS queue name (default: `high`)
- `--pbs-nodes N`: Number of nodes per job (default: `1`)
- `--pbs-ppn N`: Processors per node (default: `60`)
- `--pbs-walltime TIME`: Maximum runtime in format HH:MM:SS (default: `240:00:00`)
- `--dry-run`: Generate PBS scripts without submitting them

## How It Works

### Job Creation

When cluster mode is enabled, genomeQC creates separate PBS jobs for:

1. **TELOMERE_GAP**: Telomere and gap analysis using quartet or seqkit
2. **BUSCO_<database>**: One job per BUSCO database (allows parallel execution)
3. **LTR_ANALYSIS**: Complete LTR analysis pipeline (ltrharvest, LTR_FINDER, LTR_retriever, LAI)
4. **QUAST**: Assembly statistics and N50 calculation
5. **SYNTENY**: Synteny analysis (only if reference genome provided)

### PBS Script Structure

Each generated PBS script includes:

```bash
#!/bin/bash
#PBS -N <job_name>              # Job name
#PBS -q <queue>                 # Queue name
#PBS -l nodes=<N>:ppn=<M>       # Resource allocation
#PBS -j oe                       # Join stdout and stderr
#PBS -l walltime=<time>         # Maximum runtime

# Source bashrc for environment
source ~/.bashrc

# Navigate to working directory
cd <work_dir>
pwd
WD=`pwd`

# Setup logging
mkdir -p $WD/log
TIME=`date +%m%d_%H%M`
# Redirect stdout and stderr to log files with timestamps
exec > >(tee -a $WD/log/<job_name>_$TIME.log $WD/log/<job_name>_$TIME.out) \
     2> >(tee -a $WD/log/<job_name>_$TIME.err $WD/log/<job_name>_$TIME.out >&2)

# Note: Using 'micromamba run -n <env>' for better non-interactive execution
# Execute commands
<software-specific commands>
```

### Output Structure

```
output_directory/
├── pbs_scripts/                    # Generated PBS scripts
│   ├── TELOMERE_GAP.pbs
│   ├── BUSCO_eukaryota_odb10.pbs
│   ├── BUSCO_embryophyta_odb10.pbs
│   ├── LTR_ANALYSIS.pbs
│   ├── QUAST.pbs
│   └── SYNTENY.pbs
├── telomere_gap/
│   ├── log/                        # Job logs
│   │   ├── TELOMERE_GAP_1212_1530.log
│   │   ├── TELOMERE_GAP_1212_1530.err
│   │   └── TELOMERE_GAP_1212_1530.out
│   └── ... (analysis results)
├── busco/
│   ├── log/                        # Job logs for each BUSCO job
│   └── ... (BUSCO results)
├── ltr_analysis/
│   ├── log/                        # Job logs
│   └── ... (LTR analysis results)
├── quast/
│   ├── log/                        # Job logs
│   └── ... (QUAST results)
└── synteny/
    ├── log/                        # Job logs
    └── ... (synteny results)
```

## Examples

### Example 1: Rice Genome Assembly QC

Based on the problem statement example:

```bash
python genomeQC.py \
    --genome /data/xlxu/wuda/rice_assembly.fasta \
    --output /data/xlxu/wuda/qc_results \
    --threads 60 \
    --busco embryophyta_odb10 \
    --organism-type plant \
    --min-telomere-length 50 \
    --cluster \
    --pbs-queue high \
    --pbs-nodes 1 \
    --pbs-ppn 60 \
    --pbs-walltime 240:00:00
```

This will:
1. Generate PBS scripts in `/data/xlxu/wuda/qc_results/pbs_scripts/`
2. Submit jobs to the `high` queue
3. Each job will use 1 node with 60 processors
4. Maximum runtime of 240 hours per job
5. Logs will be saved with timestamps in each component's `log/` directory

### Example 2: Multiple BUSCO Databases

```bash
python genomeQC.py \
    --genome genome.fasta \
    --output ./results \
    --threads 60 \
    --busco eukaryota_odb10 embryophyta_odb10 metazoa_odb10 \
    --cluster \
    --pbs-queue high \
    --pbs-ppn 60
```

This creates three separate BUSCO jobs:
- `BUSCO_eukaryota_odb10.pbs`
- `BUSCO_embryophyta_odb10.pbs`
- `BUSCO_metazoa_odb10.pbs`

Each runs independently and can execute in parallel on different compute nodes.

### Example 3: With Reference Genome for Synteny

```bash
python genomeQC.py \
    --genome my_assembly.fasta \
    --output ./results \
    --threads 60 \
    --busco eukaryota_odb10 \
    --reference reference.fasta \
    --cluster \
    --pbs-queue high \
    --pbs-ppn 60
```

This adds a `SYNTENY.pbs` job for comparative genomics analysis.

## Monitoring Jobs

### Check Job Status

```bash
# Check all your jobs
qstat -u $USER

# Check specific job
qstat <job_id>

# Check detailed job information
qstat -f <job_id>
```

### View Job Logs

Logs are automatically created in timestamped files:

```bash
# View most recent log for TELOMERE_GAP job
ls -lt results/telomere_gap/log/
cat results/telomere_gap/log/TELOMERE_GAP_*.log

# View errors (if any)
cat results/telomere_gap/log/TELOMERE_GAP_*.err
```

### Delete Jobs

```bash
# Delete specific job
qdel <job_id>

# Delete all your jobs
qdel $(qstat -u $USER | grep $USER | awk '{print $1}')
```

## Best Practices

1. **Use Dry Run First**: Always test with `--dry-run` to preview generated scripts before actual submission
2. **Check Queue Limits**: Ensure your walltime and resource requests are within queue limits
3. **Monitor Resources**: Use `qstat` to monitor job progress and resource usage
4. **Review Logs**: Check log files in `<component>/log/` directories for errors
5. **Adjust Resources**: Modify `--pbs-ppn` and `--pbs-walltime` based on your genome size and queue availability

## Troubleshooting

### Jobs Not Submitting

**Problem**: Scripts generated but jobs not submitted
**Solution**: Check if `qsub` command is available and PBS/Torque is properly configured

```bash
which qsub
qstat
```

### Jobs Failing Immediately

**Problem**: Jobs submitted but fail quickly
**Solution**: Check PBS script syntax and verify software availability

```bash
# Review the PBS script
cat results/pbs_scripts/TELOMERE_GAP.pbs

# Check logs for errors
cat results/telomere_gap/log/TELOMERE_GAP_*.err
```

### Environment Issues

**Problem**: Software not found in PBS job
**Solution**: Ensure `~/.bashrc` properly initializes micromamba/conda

```bash
# Test manually
ssh <compute_node>
source ~/.bashrc
micromamba --version
```

### Insufficient Resources

**Problem**: Jobs queued but not running
**Solution**: Adjust resource requests or choose different queue

```bash
# Check queue availability
qstat -q

# Reduce resource requirements
python genomeQC.py ... --pbs-ppn 30 --pbs-walltime 120:00:00
```

## Technical Details

### Why Separate Jobs?

Each pipeline component runs as a separate job to:
- Allow parallel execution on different nodes
- Isolate failures (one component failing doesn't affect others)
- Better resource utilization (different components may have different resource needs)
- Easier monitoring and debugging

### Environment Activation

PBS scripts use `micromamba run -n <env>` instead of `micromamba activate` because:
- Works better in non-interactive shell environments
- Doesn't require shell initialization
- More reliable for PBS job execution
- Automatically handles environment setup and teardown

### Logging Strategy

The logging setup captures:
- **stdout**: Normal output → `<job>_<time>.log` and `<job>_<time>.out`
- **stderr**: Error output → `<job>_<time>.err` and `<job>_<time>.out`
- All output is also combined in `<job>_<time>.out` for convenience

## Additional Resources

- [PBS/Torque Documentation](http://docs.adaptivecomputing.com/torque/4-0-2/help.htm)
- [genomeQC README](README.md)
- [genomeQC Implementation Details](IMPLEMENTATION.md)
- [Example Usage Scripts](example_cluster_usage.sh)

## Support

For issues or questions:
1. Check the troubleshooting section above
2. Review log files in `<component>/log/` directories
3. Verify PBS script content in `pbs_scripts/` directory
4. Open an issue on GitHub with relevant log files and command used
