#!/bin/bash
# Example usage script for genomeQC pipeline in cluster mode (PBS/Torque)

# This script demonstrates how to use the genomeQC pipeline in cluster mode
# where each software or software group runs as a separate PBS job

# ============================================================================
# Example 1: Basic cluster mode with single BUSCO database
# ============================================================================
# This will generate PBS job scripts and submit them to the queue
# python genomeQC.py \
#     --genome /path/to/genome.fasta \
#     --output ./qc_results \
#     --threads 60 \
#     --busco eukaryota_odb10 \
#     --cluster \
#     --pbs-queue high \
#     --pbs-ppn 60 \
#     --pbs-walltime 240:00:00

# ============================================================================
# Example 2: Cluster mode with multiple BUSCO databases
# ============================================================================
# Each BUSCO database will run as a separate job
# python genomeQC.py \
#     --genome /path/to/genome.fasta \
#     --output ./qc_results \
#     --threads 60 \
#     --busco eukaryota_odb10 embryophyta_odb10 metazoa_odb10 \
#     --cluster \
#     --pbs-queue high \
#     --pbs-ppn 60

# ============================================================================
# Example 3: Cluster mode with reference genome for synteny analysis
# ============================================================================
# python genomeQC.py \
#     --genome /path/to/genome.fasta \
#     --output ./qc_results \
#     --threads 60 \
#     --busco eukaryota_odb10 \
#     --reference /path/to/reference.fasta \
#     --cluster \
#     --pbs-queue high \
#     --pbs-ppn 60

# ============================================================================
# Example 4: Dry run mode - generate scripts without submitting
# ============================================================================
# Use this to preview the PBS scripts that will be generated
# python genomeQC.py \
#     --genome /path/to/genome.fasta \
#     --output ./qc_results \
#     --threads 60 \
#     --busco eukaryota_odb10 \
#     --cluster \
#     --dry-run

# ============================================================================
# Example 5: Plant genome with quartet telomere analysis
# ============================================================================
# python genomeQC.py \
#     --genome /path/to/plant_genome.fasta \
#     --output ./qc_results \
#     --threads 60 \
#     --busco embryophyta_odb10 \
#     --organism-type plant \
#     --min-telomere-length 50 \
#     --cluster \
#     --pbs-queue high \
#     --pbs-ppn 60

# ============================================================================
# Example 6: Rice genome assembly QC (similar to problem statement example)
# ============================================================================
# Full example for rice genome QC with cluster mode
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

# ============================================================================
# What happens in cluster mode?
# ============================================================================
# When --cluster is enabled, the pipeline will:
# 1. Generate PBS job scripts in <output_dir>/pbs_scripts/
# 2. Each job script includes:
#    - PBS directives (#PBS -N, -q, -l, etc.)
#    - Environment setup (source ~/.bashrc)
#    - Working directory navigation
#    - Automatic log directory creation
#    - Timestamped logging (logs saved in each component's log/ directory)
# 3. Submit jobs to PBS queue (unless --dry-run is used)
# 4. Create separate jobs for:
#    - TELOMERE_GAP: Telomere and gap analysis
#    - BUSCO_<database>: One job per BUSCO database
#    - LTR_ANALYSIS: Complete LTR analysis pipeline
#    - QUAST: Assembly statistics
#    - SYNTENY: Synteny analysis (if reference genome provided)

# ============================================================================
# Checking job status
# ============================================================================
# After submitting jobs, you can check their status with:
# qstat -u $USER
# 
# Or check specific job:
# qstat <job_id>
# 
# View job output logs:
# ls -la <output_dir>/telomere_gap/log/
# ls -la <output_dir>/busco/log/
# ls -la <output_dir>/ltr_analysis/log/
# ls -la <output_dir>/quast/log/

echo "Cluster mode example script"
echo "Uncomment the examples above to use them"
