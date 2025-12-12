# Using genomeQC with Sequencing Reads

This document provides examples of using genomeQC with optional sequencing reads for Merqury QV calculation and coverage analysis.

## Overview

When sequencing reads are provided via the `--reads` parameter, genomeQC will:

1. **Run Merqury** for quality value (QV) calculation
   - Count k-mers (k=21) from reads using meryl
   - Calculate assembly QV and completeness statistics

2. **Run Coverage Analysis** using minimap2 and mosdepth
   - Align reads to assembly using minimap2
   - Convert to sorted BAM using samtools
   - Calculate coverage depth and distribution using mosdepth

## Basic Usage Examples

### Single Reads File

```bash
python genomeQC.py \
    --genome my_assembly.fasta \
    --output ./qc_results \
    --threads 16 \
    --busco eukaryota_odb10 \
    --reads reads.fastq.gz
```

### Multiple Reads Files

```bash
python genomeQC.py \
    --genome my_assembly.fasta \
    --output ./qc_results \
    --threads 16 \
    --busco eukaryota_odb10 \
    --reads reads1.fastq.gz reads2.fastq.gz reads3.fastq.gz
```

### Complete Analysis with Reference Genome

```bash
python genomeQC.py \
    --genome my_assembly.fasta \
    --output ./qc_results \
    --threads 32 \
    --busco eukaryota_odb10 embryophyta_odb10 \
    --reads long_reads.fastq.gz \
    --reference reference_genome.fasta \
    --organism-type plant \
    --min-telomere-length 50
```

## Cluster Mode Examples

### Basic Cluster Submission with Reads

```bash
python genomeQC.py \
    --genome my_assembly.fasta \
    --output ./qc_results \
    --threads 60 \
    --busco eukaryota_odb10 \
    --reads reads.fastq.gz \
    --cluster \
    --pbs-queue high \
    --pbs-ppn 60 \
    --pbs-walltime 240:00:00
```

### Dry Run (Generate Scripts Only)

```bash
python genomeQC.py \
    --genome my_assembly.fasta \
    --output ./qc_results \
    --threads 60 \
    --busco eukaryota_odb10 \
    --reads reads1.fastq.gz reads2.fastq.gz \
    --cluster \
    --dry-run
```

This generates PBS scripts in `./qc_results/pbs_scripts/` without submitting them:
- `TELOMERE_GAP.pbs`
- `BUSCO_eukaryota_odb10.pbs`
- `MERQURY.pbs` (created when reads are provided)
- `COVERAGE.pbs` (created when reads are provided)
- `LTR_ANALYSIS.pbs`
- `QUAST.pbs`

## Output Structure

When reads are provided, the output directory will include:

```
qc_results/
├── summary_report.json
├── summary_report.txt
├── merqury/
│   ├── log/                           # Job logs (cluster mode)
│   ├── my_assembly_reads.meryl/       # K-mer database
│   ├── my_assembly.qv                 # Quality value
│   ├── my_assembly.completeness.stats # Completeness statistics
│   └── *.png                          # Plots (if generated)
├── coverage/
│   ├── log/                           # Job logs (cluster mode)
│   ├── my_assembly.sorted.bam         # Aligned and sorted reads
│   ├── my_assembly.sorted.bam.bai     # BAM index
│   ├── my_assembly.mosdepth.summary.txt       # Coverage summary
│   ├── my_assembly.mosdepth.global.dist.txt   # Coverage distribution
│   └── my_assembly.mosdepth.region.dist.txt   # Per-region coverage
└── [other analysis directories...]
```

## Interpreting Results

### Merqury QV Results

The `*.qv` file contains the assembly quality value:
```
Assembly    QV
my_assembly 45.2
```

Higher QV indicates better assembly quality:
- QV 30 = 99.9% accuracy
- QV 40 = 99.99% accuracy  
- QV 50 = 99.999% accuracy

### Mosdepth Coverage Results

The `*.mosdepth.summary.txt` file contains coverage statistics:
```
chrom       length  bases      mean    min  max
chr1        1000000 25000000   25.0    0    100
chr2        800000  20000000   25.0    0    95
total       1800000 45000000   25.0    0    100
```

Key metrics:
- **mean**: Average coverage depth
- **min/max**: Coverage range
- Use the global distribution file to analyze coverage uniformity

## Notes

### Read Type Considerations

The pipeline uses `minimap2 -ax map-ont` preset for alignment, which is optimized for:
- Oxford Nanopore long reads
- PacBio HiFi reads (also works reasonably well)

For other read types, you may need to modify the preset:
- Illumina short reads: Use `-ax sr`
- PacBio CLR: Use `-ax map-pb`

### Memory Requirements

- **Merqury**: Memory usage depends on genome size and k-mer database size
  - ~50-100GB for plant genomes with 30-50x coverage
- **Minimap2**: Typically 10-20GB for large genomes
- **Mosdepth**: Relatively low memory (~2-4GB)

Adjust PBS resources accordingly in cluster mode.

### File Formats

Accepted read formats:
- FASTQ (`.fastq`, `.fq`)
- Compressed FASTQ (`.fastq.gz`, `.fq.gz`)
- FASTA (`.fasta`, `.fa`)
- Compressed FASTA (`.fasta.gz`, `.fa.gz`)

## Troubleshooting

### Merqury fails with "out of memory"

Increase memory allocation or reduce coverage by subsampling reads:
```bash
# Subsample to 30x coverage using seqtk
seqtk sample -s100 reads.fastq.gz 0.6 > reads_30x.fastq
```

### Coverage calculation takes too long

For very large genomes or high coverage:
1. Increase thread count with `-t`
2. Use cluster mode for parallel processing
3. Consider downsampling reads if coverage is >100x

### Alignment fails or produces poor results

Check read type and adjust minimap2 preset:
- View the PBS script in `./qc_results/pbs_scripts/COVERAGE.pbs`
- Modify the `-ax` parameter as needed

## Support

For issues or questions:
- Check the main [README.md](README.md) for general usage
- Review [IMPLEMENTATION.md](IMPLEMENTATION.md) for technical details
- Open an issue on GitHub
