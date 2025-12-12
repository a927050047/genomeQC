# genomeQC

Comprehensive genome quality control pipeline that evaluates genome assemblies using multiple bioinformatics tools.

## Features

- **Telomere and Gap Analysis**: Uses quartet (with visualization) or seqkit (fallback)
- **Completeness Assessment**: BUSCO analysis with support for multiple databases
- **Quality Value**: Merqury QV calculation (requires sequencing reads)
- **LTR Analysis**: ltrharvest, LTR_retriever, and LAI calculation
- **Assembly Statistics**: QUAST for N50, L50, and other metrics
- **Synteny Analysis**: GenomeSyn for comparative genomics (optional)

## Requirements

- Python 3.6+
- micromamba (recommended for dependency management) or environment modules
- Optional: quartet, GenomeSyn (special tools not managed by conda)

### Tool Dependencies

The pipeline automatically manages dependencies using micromamba:
- seqkit
- busco
- merqury
- genometools (for ltrharvest)
- ltr_retriever
- quast

## Installation

1. Clone the repository:
```bash
git clone https://github.com/a927050047/genomeQC.git
cd genomeQC
```

2. Make the script executable:
```bash
chmod +x genomeQC.py
```

3. Install micromamba (if not already installed):
```bash
curl -Ls https://micro.mamba.pm/api/micromamba/linux-64/latest | tar -xvj bin/micromamba
```

## Usage

### Basic Usage

```bash
python genomeQC.py -g genome.fasta -o results -t 16 -b eukaryota_odb10
```

### With Multiple BUSCO Databases

```bash
python genomeQC.py -g genome.fasta -o results -t 16 -b eukaryota_odb10 bacteria_odb10 fungi_odb10
```

### With Local BUSCO Database

```bash
python genomeQC.py -g genome.fasta -o results -t 16 -b /path/to/busco_downloads/lineages/eukaryota_odb10
```

### With Reference Genome for Synteny Analysis

```bash
python genomeQC.py -g genome.fasta -o results -t 16 -b eukaryota_odb10 -r reference.fasta
```

### Full Example

```bash
python genomeQC.py \
    --genome my_assembly.fasta \
    --output ./qc_results \
    --threads 32 \
    --busco eukaryota_odb10 metazoa_odb10 \
    --reference reference_genome.fasta
```

## Command Line Arguments

- `-g, --genome`: Input genome FASTA file (required)
- `-o, --output`: Output directory for results (required)
- `-t, --threads`: Number of threads to use (default: 1)
- `-b, --busco`: BUSCO database(s) - can specify multiple databases or local paths (required)
- `-r, --reference`: Reference genome for synteny analysis (optional)

## Output Structure

```
output_directory/
├── summary_report.json          # JSON format summary
├── summary_report.txt           # Human-readable summary
├── telomere_gap/               # Telomere and gap analysis results
│   ├── quartet_output/         # (if quartet available)
│   └── seqkit_stats.tsv        # (if using seqkit fallback)
├── busco/                      # BUSCO completeness results
│   ├── busco_eukaryota_odb10/
│   └── ...
├── merqury/                    # Merqury QV results
├── ltr_analysis/               # LTR and LAI analysis
│   ├── ltrharvest.out
│   ├── ltrharvest.gff3
│   └── ...
├── quast/                      # QUAST assembly statistics
│   ├── report.txt
│   ├── report.html
│   └── ...
└── synteny/                    # Synteny plots (if reference provided)
```

## Environment Management

The pipeline uses intelligent environment management:

1. **Existing Environment Check**: Checks for existing micromamba environments (case-insensitive)
2. **Module System Check**: Falls back to environment modules if available
3. **Automatic Installation**: Creates new micromamba environments if needed
4. **System Fallback**: Uses system-installed tools as last resort

### Special Tools

- **quartet**: Must be installed separately (not available in conda)
  - If unavailable, pipeline uses seqkit as fallback (no visualization)
- **GenomeSyn**: Must be installed separately (not available in conda)
  - If unavailable and reference genome provided, pipeline issues warning and skips

## Notes

- **Merqury QV**: Requires raw sequencing reads for k-mer database generation (currently skipped if reads not provided)
- **LAI Calculation**: Requires additional LAI software installation
- **quartet**: Provides visualization capabilities for telomere analysis; fallback to seqkit for basic stats only
- **GenomeSyn**: Only runs when both the tool and reference genome are available

## Citation

If you use this pipeline, please cite the individual tools:

- BUSCO: Manni et al. (2021)
- QUAST: Gurevich et al. (2013)
- seqkit: Shen et al. (2016)
- Merqury: Rhie et al. (2020)
- LTR_retriever: Ou & Jiang (2018)
- GenomeTools: Gremme et al. (2013)

## License

MIT License

## Contact

For issues and questions, please open an issue on GitHub.
