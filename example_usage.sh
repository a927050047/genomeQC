#!/bin/bash
# Example usage script for genomeQC pipeline

# This script demonstrates how to run the genomeQC pipeline
# Adjust the paths and parameters according to your data

# Example 1: Basic usage with single BUSCO database
# python genomeQC.py \
#     --genome /path/to/genome.fasta \
#     --output ./results \
#     --threads 16 \
#     --busco eukaryota_odb10

# Example 2: Multiple BUSCO databases
# python genomeQC.py \
#     --genome /path/to/genome.fasta \
#     --output ./results \
#     --threads 32 \
#     --busco eukaryota_odb10 metazoa_odb10 fungi_odb10

# Example 3: With reference genome for synteny analysis
# python genomeQC.py \
#     --genome /path/to/genome.fasta \
#     --output ./results \
#     --threads 32 \
#     --busco eukaryota_odb10 \
#     --reference /path/to/reference.fasta

# Example 4: Using local BUSCO database
# python genomeQC.py \
#     --genome /path/to/genome.fasta \
#     --output ./results \
#     --threads 16 \
#     --busco /path/to/busco_downloads/lineages/eukaryota_odb10

# Example 5: Full pipeline with all options
python genomeQC.py \
    --genome genome.fasta \
    --output qc_results \
    --threads 32 \
    --busco eukaryota_odb10 metazoa_odb10 \
    --reference reference.fasta

echo "Pipeline execution completed!"
echo "Check the results in the output directory"
